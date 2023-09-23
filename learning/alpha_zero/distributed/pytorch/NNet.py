import copy
from metaMinichess.games.gardner.GardnerMiniChessGame import GardnerMiniChessGame
import os
import sys
import time

import numpy as np
from numpy.lib.function_base import average
from tqdm import tqdm

from metaMinichess.learning.alpha_zero.distributed.utils import *
from metaMinichess.learning.alpha_zero.distributed.pytorch.NeuralNet import NeuralNet

import torch
import torch.optim as optim

from .MCGardnerNNet import MCGardnerNNet as mcnet

# LEN_ACTION_SPACE = 1225

class NNetWrapper(NeuralNet):
    def __init__(self, game):
        self.nnet = mcnet(game)
        self.game = game
        self.board_x, self.board_y = (5, 5)
        self.action_size = GardnerMiniChessGame().getActionSize()
        self.args={'cuda':False}

        # self.args = args.copy()

        # if self.args['cuda']: # can't happen with multiprocessing
        #     self.nnet.cuda()

    def train(self, examples):
        """
        examples: list of examples, each example is of form (board, pi, v)
        """
        optimizer = optim.Adam(self.nnet.parameters())

        if self.args['cuda']: # this is not multiprocessed so we can use CUDA
            self.nnet = self.nnet.cuda()

        losses = []

        for epoch in range(self.args['epochs']):
            print('EPOCH ::: ' + str(epoch + 1))
            self.nnet.train()
            pi_losses = AverageMeter()
            v_losses = AverageMeter()

            batch_count = int(len(examples) / self.args['batch_size'])

            t = tqdm(range(batch_count), desc='Training Net')
            for _ in t:
                sample_ids = np.random.randint(len(examples), size=self.args['batch_size'])
                boards, pis, vs = list(zip(*[examples[i] for i in sample_ids]))
                boards = torch.FloatTensor(np.array(boards).astype(np.float64))
                target_pis = torch.FloatTensor(np.array(pis))
                target_vs = torch.FloatTensor(np.array(vs).astype(np.float64))

                # predict
                if self.args['cuda']: # this is not multiprocessed so we can use CUDA
                    boards, target_pis, target_vs = boards.contiguous().cuda(), target_pis.contiguous().cuda(), target_vs.contiguous().cuda()

                # compute output
                out_pi, out_v = self.nnet(boards)
                l_pi = self.loss_pi(target_pis, out_pi)
                l_v = self.loss_v(target_vs, out_v)
                total_loss = l_pi + l_v

                # record loss
                pi_losses.update(l_pi.item(), boards.size(0))
                v_losses.update(l_v.item(), boards.size(0))
                t.set_postfix(Loss_pi=pi_losses, Loss_v=v_losses)

                # compute gradient and do SGD step
                optimizer.zero_grad()
                total_loss.backward()
                optimizer.step()
            losses.append((pi_losses.avg,v_losses.avg))

        # back to CPU
        self.nnet = self.nnet.cpu()

        return losses

    def predict(self, board):
        """
        board: np array with board
        """
        # timing
        start = time.time()

        board = np.array(board)
        board = board[np.newaxis, :, :]
        # preparing input
        board = torch.FloatTensor(board.astype(np.float64))
        # if self.args['cuda']: board = board.contiguous().cuda() # does not work with multiprocessing
        board = board.view(1, self.board_x, self.board_y)
        self.nnet.eval()
        with torch.no_grad():
            pi, v = self.nnet(board)

        # print('PREDICTION TIME TAKEN : {0:03f}'.format(time.time()-start))
        return torch.exp(pi).data.cpu().numpy()[0], v.data.cpu().numpy()[0]

    def loss_pi(self, targets, outputs):
        return -torch.sum(targets * outputs) / targets.size()[0]

    def loss_v(self, targets, outputs):
        return torch.sum((targets - outputs.view(-1)) ** 2) / targets.size()[0]

    def save_checkpoint(self, folder='checkpoint', filename='checkpoint.pth.tar'):
        filepath = os.path.join(folder, filename)
        if not os.path.exists(folder):
            print("Checkpoint Directory does not exist! Making directory {}".format(folder))
            os.mkdir(folder)
        else:
            print("Checkpoint Directory exists! ")
        torch.save({
            'state_dict': self.nnet.state_dict(),
        }, filepath)

    def load_checkpoint(self, folder='checkpoint', filename='checkpoint.pth.tar'):
        # https://github.com/pytorch/examples/blob/master/imagenet/main.py#L98
        filepath = os.path.join(folder, filename)
        if not os.path.exists(filepath):
            raise ValueError("No model in path {}".format(filepath))
        map_location = None if self.args['cuda'] else 'cpu'
        checkpoint = torch.load(filepath, map_location=map_location)
        self.nnet.load_state_dict(checkpoint['state_dict'])

    def state_dict(self):
        '''
            Returns
            -------
            The state_dict of self.nnet
        '''
        return self.nnet.state_dict()

    def load_average_params(self, state_dicts):
        '''
            Given a list of state_dicts, take the average across them all
            and set self.nnet's weights as this average.

            Returns
            -------
            the average state_dict
        '''

        first_dict = state_dicts[0]

        avg_dict = {}

        for key in first_dict:
            avg_dict[key] = torch.mean(torch.stack([d[key].float() for d in state_dicts]), 0)

        self.nnet.load_state_dict(avg_dict)


        return avg_dict

    def __getstate__(self):
        self_dict = self.__dict__.copy()
        if 'pool' in self_dict: del self_dict['pool']
        return self_dict

    def __deepcopy__(self, memo):
        net = NNetWrapper(self.game, self.args.copy())
        net.nnet = copy.deepcopy(self.nnet, memo)
        net.board_x = self.board_x
        net.board_y = self.board_y
        net.action_size = self.action_size
        return net

import enum
from minichess.pieces import Piece, PieceColor, Pawn, Knight, Bishop, Rook, King, Queen, MiniChessMove
from minichess.state import MiniChessState
import numpy as np

class ActionType(enum.Enum):
    KNIGHTWISE = 1
    MAJOR_DIAG = 2
    MINOR_DIAG = 3
    VERTICALLY = 4
    HORIZONTAL = 5


# Dictionary mapping argmaxes of one-hots to appropriate Piece Constructor / ID
PIECE_DICT = {
    PieceColor.WHITE: {
        0: (Pawn, 0),
        1: (Pawn, 1),
        2: (Pawn, 2),
        3: (Pawn, 3),
        4: (Pawn, 4),
        5: (Rook, 5),
        6: (Knight, 6),
        7: (Bishop, 7),
        8: (Queen, 8),
        9: (King, 9)
    },
    PieceColor.BLACK: {
        0: (Pawn, 10),
        1: (Pawn, 11),
        2: (Pawn, 12),
        3: (Pawn, 13),
        4: (Pawn, 14),
        5: (Rook, 15),
        6: (Knight, 16),
        7: (Bishop, 17),
        8: (Queen, 18),
        9: (King, 19)
    }
}
# Dictionary mapping argmaxes of one-hots to appropriate action types
TYPE_DICT = {
    0: ActionType.KNIGHTWISE,
    1: ActionType.MAJOR_DIAG,
    2: ActionType.MINOR_DIAG,
    3: ActionType.VERTICALLY,
    4: ActionType.HORIZONTAL
}

# Dictionary mapping argmaxes of one-hots to appropriate magnitudes
MAG_DICT = {
    0: -4,
    1: -3,
    2: -2,
    3: -1,
    4: 1,
    5: 2,
    6: 3,
    7: 4
}

INVALID_MOVE = MiniChessMove((-1, -1), (-1, -1)) # a guaranteed invalid move

class MiniChessAction:
    '''
        Class representing action a ∈ A, where A is the action space of a MiniChess agent, and
        a is a tuple (p, t, m) with p = piece to move, t = type of move, m = magnitude. By
        structuring our actions / action space this way, our players only ever have at most

        `10 pieces + 5 types of move + 8 magnitudes` to choose from.

        Pieces: A player has 5 pawns, 1 Knight, 1 Bishop, 1 Rook, 1 Queen, 1 King

        Types of Move: A piece in the abstarct can move "knight-wise", on the major diagonal, on 
        the minor diagonal, vertically, or horizontally. In reality, the types of move are more
        restrictive and will be penalized accordingly.

        Magnitude: On the extermes, a piece can only ever move at most 4 or -4 tiles away.
    '''

    def __init__(self, piece: Piece, _type: ActionType, magnitude: int):
        self.piece = piece
        self._type = _type
        self.magnitude = magnitude

    @staticmethod
    def from_vectors(color: PieceColor, piece_vector: np.array, type_vector: np.array, mag_vector: np.array):
        '''
            Static Constructor for `MiniChessAction` from output vectors of our neural net.

            Parameters
            ----------
            color :: PieceColor : the color moving
            
            piece_vector :: np array of shape (10,) : one hot describing the piece to move

            type_vector :: np array of shape (5,) : one hot describing the type of move to make

            magnitude_vector :: np array of shape (8,) : one hot describing the magnitude of the move

            Returns
            -------
            A new `MiniChessAction` object representing the input vectors.
        '''
        constructor, _id = PIECE_DICT[np.argmax(piece_vector)] # get the constructor method and id based off of model predictions
        dummy_piece = constructor(_id, color)
        
        _type = TYPE_DICT[np.argmax(type_vector)]
        
        magnitude = MAG_DICT[np.argmax(mag_vector)]

        return MiniChessAction(dummy_piece, _type, magnitude)

    def to_minichess_move(self, state: MiniChessState):
        '''
            Convert to a `MiniChessMove`.

            Parameters
            ----------
            state :: MiniChessState : the current state of the Minichess game

            Returns
            -------
            `MiniChessMove` representing this `MiniChessAction`
        '''
        found_piece = state.find_piece(self.piece)

        if found_piece == (-1, -1): return INVALID_MOVE # this piece is not on the board

        row,col = found_piece

        real_piece = state.board[row][col]

        new_row, new_col = self._calculate_new_pos(row, col, self._type, self.magnitude)

        return MiniChessMove((row, col), (new_row, new_col), real_piece)

    def _calculate_new_pos(self, row, col, _type, magnitude):
        if _type == ActionType.KNIGHTWISE: # this is a special case
            if magnitude == -4:
                return row - 2, col - 1
            elif magnitude == -3:
                return row - 1, col - 2
            elif magnitude == -2:
                return row + 1, col - 2
            elif magnitude == -1:
                return row + 2, col - 1
            elif magnitude == 1:
                return row + 2, col + 1
            elif magnitude == 2:
                return row + 1, col + 2
            elif magnitude == 3:
                return row - 1, col + 2
            elif magnitude == 4:
                return row - 2, col + 1

        elif _type == ActionType.MAJOR_DIAG: # SW -> NE
            return row - magnitude, col + magnitude

        elif _type == ActionType.MINOR_DIAG: # SE -> NW
            return row - magnitude, col - magnitude

        elif _type == ActionType.HORIZONTAL: # W -> E
            return row, col + magnitude

        elif _type == ActionType.VERTICALLY: # S -> N
            return row - magnitude, col

        raise RuntimeError('Could not calculate new position of invalid ActionType {}'.format(type(_type)))

    def is_valid_action(self, state: MiniChessState):
        '''
            Verify whether or not this is a valid action to take.

            Parameters
            ----------
            state :: MiniChessState : the current state of the Minichess game

            Returns
            -------
            True if this action results in a valid next state (i.e. it can be taken), False otherwise
        '''
        move = self.to_minichess_move(state)

        next_moves = state.possible_next_states(self.piece.color)

        return move in next_moves


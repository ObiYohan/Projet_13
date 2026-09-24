import chess

from .lichess_service import LichessService
from .stockfish_service import StockfishService


def parse_fen(fen: str) -> chess.Board:
    """Parse and validate a FEN string, raising ValueError if it is invalid."""
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise ValueError(f"Invalid FEN '{fen}': {exc}") from exc
    if not board.is_valid():
        raise ValueError(f"Illegal chess position for FEN '{fen}'.")
    return board


class ChessAgentService:
    """Main agent logic: theoretical moves via Lichess, position evaluation via Stockfish."""

    def __init__(
        self,
        lichess_service: LichessService | None = None,
        stockfish_service: StockfishService | None = None,
    ) -> None:
        self._lichess = lichess_service or LichessService()
        self._stockfish = stockfish_service or StockfishService()

    async def get_theoretical_moves(self, fen: str) -> dict:
        board = parse_fen(fen)
        raw_moves = await self._lichess.get_opening_moves(board.fen())

        moves = [
            {
                "uci": move["uci"],
                "san": board.san(chess.Move.from_uci(move["uci"])),
                "white": move["white"],
                "draws": move["draws"],
                "black": move["black"],
            }
            for move in raw_moves
            if board.is_legal(chess.Move.from_uci(move["uci"]))
        ]

        return {"fen": board.fen(), "moves": moves}

    async def evaluate_position(self, fen: str) -> dict:
        board = parse_fen(fen)
        evaluation = await self._stockfish.evaluate(board)
        return {
            "fen": board.fen(),
            "turn": "white" if board.turn == chess.WHITE else "black",
            **evaluation,
        }

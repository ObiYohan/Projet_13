import asyncio
import os

import chess
import chess.engine

DEFAULT_STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "stockfish")
DEFAULT_DEPTH = 15


class StockfishServiceError(Exception):
    """Base error for failures while running the Stockfish engine."""


class StockfishService:
    """Encapsulates calls to a local Stockfish engine via the UCI protocol."""

    def __init__(
        self,
        engine_path: str = DEFAULT_STOCKFISH_PATH,
        depth: int = DEFAULT_DEPTH,
        timeout: float = 10.0,
    ) -> None:
        self._engine_path = engine_path
        self._depth = depth
        self._timeout = timeout

    async def evaluate(self, board: chess.Board) -> dict:
        """Analyse `board` and return its evaluation from white's point of view."""
        try:
            transport, engine = await asyncio.wait_for(
                chess.engine.popen_uci(self._engine_path), timeout=self._timeout
            )
        except FileNotFoundError as exc:
            raise StockfishServiceError(
                f"Could not find the Stockfish engine at '{self._engine_path}'."
            ) from exc
        except asyncio.TimeoutError as exc:
            raise StockfishServiceError("Timed out starting the Stockfish engine.") from exc

        try:
            info = await asyncio.wait_for(
                engine.analyse(board, chess.engine.Limit(depth=self._depth)),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as exc:
            raise StockfishServiceError("Stockfish analysis timed out.") from exc
        except chess.engine.EngineError as exc:
            raise StockfishServiceError(f"Stockfish engine error: {exc}") from exc
        finally:
            await engine.quit()

        score = info["score"].white()
        depth = info.get("depth", self._depth)
        if score.is_mate():
            return {"depth": depth, "cp": None, "mate": score.mate()}
        return {"depth": depth, "cp": score.score(), "mate": None}

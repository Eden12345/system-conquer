import uuid
from typing import Dict

from .game_state import GameState

games: Dict[str, GameState] = {}

def create_game(radius: int = 3):
    gid = str(uuid.uuid4())
    games[gid] = GameState(radius)
    return gid, games[gid]

def get_game(gid: str):
    return games.get(gid)
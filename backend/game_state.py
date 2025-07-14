import random
from typing import Dict, Tuple
from fastapi import WebSocket

from .utils import neighbors
from .models import PlayerState
from .constants import CARD_COST

class GameState:
    def __init__(self, radius: int = 3):
        self.radius = radius
        # build empty hex board
        self.board: Dict[Tuple[int,int], dict] = {}
        for q in range(-radius, radius+1):
            for r in range(-radius, radius+1):
                if abs(q+r) <= radius:
                    self.board[(q,r)] = {"owner": None, "unit": None, "health": 0}

        # two players
        self.players = {
            "bottom": PlayerState(),
            "top":    PlayerState(),
        }
        self.turn = "bottom"
        self.started = False
        self.sockets: Dict[str, WebSocket] = {}

    def add_player(self, ws: WebSocket) -> str:
        role = "bottom" if "bottom" not in self.sockets else "top"
        self.sockets[role] = ws
        return role

    def remove_player(self, role: str):
        self.sockets.pop(role, None)

    async def start(self):
        self.started = True
        for ps in self.players.values():
            ps.draw_start()
        await self.broadcast_state()

    async def broadcast_state(self):
        state = {
            "type": "state",
            "board": [
                {"q": q, "r": r, **info}
                for (q,r),info in self.board.items()
            ],
            "players": {
                role: {
                    "hand": [c.type for c in ps.hand],
                    "actions_left": ps.actions_left,
                    "bases_remaining": ps.bases_remaining,
                }
                for role,ps in self.players.items()
            },
            "turn": self.turn,
        }
        for ws in self.sockets.values():
            await ws.send_json(state)

    async def handle_action(self, role: str, data: dict):
        if data.get("action") != "play_card": return
        if role != self.turn:               return

        ps = self.players[role]
        for card in list(ps.hand):
            if card.type == data["card_type"]:
                if ps.actions_left < card.cost: return

                if card.type in ("create_base","create_ship"):
                    await self._create_unit(role, data, card)
                elif card.type == "move":
                    await self._move_unit(role, data, card)
                elif card.type == "attack":
                    await self._attack(role, data, card)
                break

    async def _create_unit(self, role, data, card):
        target = (data["target"]["q"], data["target"]["r"])
        tile = self.board.get(target)
        if not tile or tile["unit"]: return

        unit = "base" if card.type=="create_base" else "ship"
        # ship needs adjacent base; base needs adjacent any unit
        if unit=="ship":
            valid = any(
                self.board.get(nb,{}).get("unit")=="base" and self.board[nb]["owner"]==role
                for nb in neighbors(*target)
            )
        else:
            valid = any(
                self.board.get(nb,{}).get("owner")==role
                for nb in neighbors(*target)
            )
        if not valid: return

        tile.update({
            "unit": unit,
            "owner": role,
            "health": 3 if unit=="ship" else 5
        })
        if unit=="base":
            self.players[role].bases_remaining += 1

        await self._post_action(role, card)

    async def _move_unit(self, role, data, card):
        src = (data["src"]["q"], data["src"]["r"])
        dst = (data["target"]["q"], data["target"]["r"])
        t0, t1 = self.board.get(src), self.board.get(dst)
        if not t0 or not t1:                  return
        if t0["owner"]!=role or t0["unit"]!="ship" or t1["unit"]: return
        if dst not in neighbors(*src):        return

        # do move
        t1.update({"unit":"ship","owner":role,"health":t0["health"]})
        t0.update({"unit":None,"owner":None,"health":0})

        # immediate base auto‑damage on adjacency
        for nb in neighbors(*dst):
            nb_tile = self.board.get(nb)
            if nb_tile and nb_tile["unit"]=="base" and nb_tile["owner"]!=role:
                nb_tile["health"] -= 1
                if nb_tile["health"] <= 0:
                    self.players[nb_tile["owner"]].bases_remaining -= 1
                    nb_tile.update({"unit":None,"owner":None,"health":0})

        await self._post_action(role, card)

    async def _attack(self, role, data, card):
        src = (data["src"]["q"], data["src"]["r"])
        tgt = (data["target"]["q"], data["target"]["r"])
        t0, t1 = self.board.get(src), self.board.get(tgt)
        if not t0 or not t1:                       return
        if t0["owner"]!=role or not t1["unit"] or t1["owner"]==role: return
        if tgt not in neighbors(*src):             return

        t1["health"] -= 1
        if t1["health"] <= 0:
            if t1["unit"]=="base":
                self.players[t1["owner"]].bases_remaining -= 1
            t1.update({"unit":None,"owner":None,"health":0})

        await self._post_action(role, card)

    async def _post_action(self, role, card):
        ps = self.players[role]
        ps.actions_left -= card.cost
        ps.discard.append(card)
        ps.hand.remove(card)
        ps.draw_start()

        # turn switch
        if ps.actions_left <= 0:
            self.turn = "top" if role=="bottom" else "bottom"
            next_ps = self.players[self.turn]
            next_ps.actions_left = 3
            next_ps.draw_start()

        await self.broadcast_state()
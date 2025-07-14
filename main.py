import uuid
import random
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from typing import Dict, Tuple

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# In‐memory store of all games
games: Dict[str, "GameState"] = {}

# --- Game Data Models ---

CARD_COUNTS = {
    "create_base": 2,
    "create_ship": 3,
    "move": 4,
    "attack": 4,
}
CARD_COST = {
    "create_base": 3,
    "create_ship": 2,
    "move": 1,
    "attack": 1,
}

def neighbors(q: int, r: int):
    # axial hex neighbors
    for dq, dr in [(+1,0), (+1,-1), (0,-1), (-1,0), (-1,+1), (0,+1)]:
        yield q + dq, r + dr

class Card:
    def __init__(self, type: str):
        self.type = type
        self.cost = CARD_COST[type]

class PlayerState:
    def __init__(self):
        # build deck
        deck = []
        for t,count in CARD_COUNTS.items():
            deck += [Card(t) for _ in range(count)]
        random.shuffle(deck)
        self.deck = deck
        self.hand: list[Card] = []
        self.discard: list[Card] = []
        self.actions_left = 3
        self.bases_remaining = 0

    def draw_start(self):
        # draw up to 4
        while len(self.hand) < 4 and self.deck:
            self.hand.append(self.deck.pop())
        if not self.deck:
            random.shuffle(self.discard)
            self.deck, self.discard = self.discard, []

class GameState:
    def __init__(self, radius=3):
        self.radius = radius
        # board coords → { owner, unit, health }
        self.board: Dict[Tuple[int,int], dict] = {}
        for q in range(-radius, radius+1):
            for r in range(-radius, radius+1):
                if abs(q+r) <= radius:
                    self.board[(q,r)] = {"owner": None, "unit": None, "health": 0}

        # two players
        self.players = {"bottom": PlayerState(), "top": PlayerState()}
        self.turn = "bottom"
        self.started = False
        self.sockets: Dict[str, WebSocket] = {}

    def add_player(self, ws: WebSocket):
        role = "bottom" if "bottom" not in self.sockets else "top"
        self.sockets[role] = ws
        return role

    def remove_player(self, role: str):
        self.sockets.pop(role, None)

    async def start(self):
        self.started = True
        # initial draws
        for p in self.players.values():
            p.draw_start()
        await self.broadcast_state()

    async def broadcast_state(self):
        state = {
            "type": "state",
            "board": [
                {"q": q, "r": r, **info}
                for (q,r), info in self.board.items()
            ],
            "players": {
                role: {
                    "hand": [c.type for c in ps.hand],
                    "actions_left": ps.actions_left,
                    "bases_remaining": ps.bases_remaining,
                }
                for role, ps in self.players.items()
            },
            "turn": self.turn,
        }
        for ws in self.sockets.values():
            await ws.send_json(state)

    async def handle_action(self, role: str, data: dict):
        if data.get("action") != "play_card":
            return
        if role != self.turn:
            return  # not your turn
        ps = self.players[role]
        # find card in hand
        for i,card in enumerate(ps.hand):
            if card.type == data["card_type"]:
                if ps.actions_left < card.cost:
                    return
                target = (data["target"]["q"], data["target"]["r"])
                # validate & apply
                if card.type == "create_ship":
                    await self._create_unit(role, target, "ship", card)
                elif card.type == "create_base":
                    await self._create_unit(role, target, "base", card)
                elif card.type == "move":
                    await self._move_unit(role, data, card)
                elif card.type == "attack":
                    await self._attack(role, data, card)
                break

    async def _create_unit(self, role, target, unit_type, card):
        tile = self.board.get(target)
        if not tile or tile["unit"]:
            return
        # must be adjacent to your base for ship,
        # or adjacent to any your unit for base
        if unit_type=="ship":
            ok = any(
                self.board.get(nb,{}).get("unit")=="base" and self.board[nb]["owner"]==role
                for nb in neighbors(*target)
            )
        else:
            ok = any(
                self.board.get(nb,{}).get("owner")==role
                for nb in neighbors(*target)
            )
        if not ok:
            return
        # place
        tile["unit"] = unit_type
        tile["owner"] = role
        tile["health"] = 3 if unit_type=="ship" else 5
        self.players[role].bases_remaining += (1 if unit_type=="base" else 0)
        await self._post_action(role, card)

    async def _move_unit(self, role, data, card):
        src = (data["src"]["q"], data["src"]["r"])
        dst = (data["target"]["q"], data["target"]["r"])
        if dst not in self.board or src not in self.board:
            return
        t0, t1 = self.board[src], self.board[dst]
        if t0["owner"]!=role or t0["unit"]!="ship" or t1["unit"]:
            return
        if dst not in neighbors(*src):
            return
        # move
        t1.update({"unit":"ship", "owner":role, "health": t0["health"]})
        t0.update({"unit":None, "owner":None, "health":0})
        # auto‐attack by adjacent enemy bases
        for nb in neighbors(*dst):
            nb_tile = self.board.get(nb)
            if nb_tile and nb_tile["unit"]=="base" and nb_tile["owner"]!=role:
                nb_tile["health"] -= 1
                if nb_tile["health"] <= 0:
                    # base destroyed
                    self.players[nb_tile["owner"]].bases_remaining -= 1
                    nb_tile.update({"unit":None, "owner":None, "health":0})
        await self._post_action(role, card)

    async def _attack(self, role, data, card):
        src = (data["src"]["q"], data["src"]["r"])
        tgt = (data["target"]["q"], data["target"]["r"])
        if tgt not in self.board or src not in self.board:
            return
        t0, t1 = self.board[src], self.board[tgt]
        if t0["owner"]!=role or not t1["unit"] or t1["owner"]==role:
            return
        if tgt not in neighbors(*src):
            return
        t1["health"] -= 1
        if t1["health"] <= 0:
            # track base loss
            if t1["unit"]=="base":
                self.players[t1["owner"]].bases_remaining -= 1
            t1.update({"unit":None, "owner":None, "health":0})
        await self._post_action(role, card)

    async def _post_action(self, role, card):
        ps = self.players[role]
        # deduct actions
        ps.actions_left -= card.cost
        # move card to discard
        ps.discard.append(card)
        ps.hand.remove(card)
        # draw replacement immediately
        ps.draw_start()
        # recalc control (not implemented here, placeholder)
        # self._recalculate_control()
        # check for win
        # self._check_win()
        # if turn over:
        if ps.actions_left <= 0:
            self.turn = "top" if role=="bottom" else "bottom"
            self.players[self.turn].actions_left = 3
            self.players[self.turn].draw_start()
        # broadcast updated state
        await self.broadcast_state()


# --- HTTP + WebSocket endpoints ---

@app.post("/create")
async def create_game():
    gid = str(uuid.uuid4())
    games[gid] = GameState(radius=3)
    return {"game_id": gid, "url": f"/static/index.html?game={gid}"}

@app.websocket("/ws/{game_id}")
async def websocket_endpoint(ws: WebSocket, game_id: str):
    await ws.accept()
    game = games.get(game_id)
    if not game:
        await ws.close()
        return
    role = game.add_player(ws)
    # once two are in, start
    if len(game.sockets) == 2 and not game.started:
        await game.start()
    try:
        while True:
            data = await ws.receive_json()
            await game.handle_action(role, data)
    except WebSocketDisconnect:
        game.remove_player(role)
        # forfeit logic
        if game.started and game.sockets:
            other = next(iter(game.sockets.values()))
            await other.send_json({"type": "forfeit_win"})
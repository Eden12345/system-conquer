from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .game_manager import create_game, get_game

router = APIRouter()

@router.post("/create")
async def create_game_endpoint():
    gid, _ = create_game()
    return {"game_id": gid, "url": f"/static/index.html?game={gid}"}

@router.websocket("/ws/{game_id}")
async def websocket_endpoint(ws: WebSocket, game_id: str):
    await ws.accept()
    game = get_game(game_id)
    if not game:
        await ws.close()
        return

    role = game.add_player(ws)
    # start once two are present
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
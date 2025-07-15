# System Conquer

A multiplayer, turn-based strategy game with deck-building elements built with a Python (FastAPI) backend and a vanilla HTML/CSS/JS frontend. Being in the early prototyping stage, it currently runs the game in-memory and has a static card deck for each player.

## Game Mechanics

- **Board**: A diamond-shaped hex grid (radius 3 by default), viewed from each player's perspective—you're at the bottom, your opponent at the top.
- **Units**:

  - **Ship**: 3 health, must be created adjacent to one of your bases.
  - **Base**: 5 health, must be created adjacent to any of your existing units.

- **Cards & Actions**:

  - Each player has a 13-card deck:

    - Create Base (3 action cost) × 2 cards
    - Create Ship (2 action cost) × 3 cards
    - Move Ship (1 action cost) × 4 cards
    - Attack (1 action cost) × 4 cards

  - You draw 4 cards at the start of your turn and have 3 action points available.
  - **Playing a card** consumes its action cost and triggers one of:

    - **Create** a ship/base on a valid adjacent hex.
    - **Move** a ship to an adjacent empty hex. When a ship enters a hex adjacent to an enemy base, it immediately deals 1 damage to that base.
    - **Attack** an adjacent enemy unit (ship or base) for 1 damage.

- **Turn Flow**:

  1. Refill hand to 4 cards (reshuffle discard if needed).
  2. Set action points to 3.
  3. Play cards until action points are exhausted or you end turn early.
  4. Pass turn to opponent, who draws/refreshes accordingly.

- **Winning Conditions**:

  - Destroy all of your opponent's bases.
  - Control ≥ 75% of the board’s hexes (any tile adjacent to your units, excluding contested hexes that touch both players).

- **Forfeiture**: If a player disconnects after the game has started, they forfeit and the opponent immediately wins.

## Project Setup

### Prerequisites

- Python 3.8 or higher
- `pip` package manager

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/YOUR_USER/hex-deck-proto.git
   cd hex-deck-proto
   ```

2. **Create and activate a virtual environment** (optional but recommended)

   ```bash
   python3 -m venv venv
   source venv/bin/activate    # macOS/Linux
   venv\\Scripts\\activate   # Windows
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

### Running the Server

Start the FastAPI backend with Uvicorn:

```bash
uvicorn main:app --reload
```

- The server listens on `http://127.0.0.1:8000/` by default.
- Static frontend files are served from `/static/index.html`.

### Playing the Game

1. In your browser, open:
   `http://127.0.0.1:8000/static/index.html`

2. Click **Create Game** to generate a new session link.

3. Share the link (or open it in another tab/browser) to join as the second player.

4. Select cards from your hand and click on hexes to perform actions.

5. Watch real‑time updates via WebSocket; disconnecting forfeits.

## Next Steps

- Implement control‑tile calculation and territory victory.
- Add persistence (Redis or a database) to survive server restarts.
- Introduce timers, UI polish, and animations.
- Extend deck with new card types and rarities.
- Create larger infrastructure for civilizations that consist of multiple players and tracks their progress across a scalable amount of systems.

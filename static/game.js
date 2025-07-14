// --- Helpers ---
function qs(sel) {
  return document.querySelector(sel);
}
function qsa(sel) {
  return [...document.querySelectorAll(sel)];
}

function getParam(name) {
  const params = new URLSearchParams(location.search);
  return params.get(name);
}

// axial → pixel
function axialToPixel(q, r) {
  const size = 35;
  const x = size * (Math.sqrt(3) * q + (Math.sqrt(3) / 2) * r) + 300;
  const y = size * ((3 / 2) * r) + 300;
  return { x, y };
}

function hexPolygon(x, y, size = 35) {
  let pts = [];
  for (let i = 0; i < 6; i++) {
    const ang = (Math.PI / 180) * (60 * i - 30);
    pts.push(`${x + size * Math.cos(ang)},${y + size * Math.sin(ang)}`);
  }
  return pts.join(" ");
}

// --- UI References ---
const lobby = qs("#lobby"),
  gameDiv = qs("#game");
const btnCreate = qs("#btn-create");
const svg = qs("#board");
const turnEl = qs("#turn"),
  actionsEl = qs("#actions"),
  basesEl = qs("#bases");
const handDiv = qs("#hand");

let ws,
  selectedCard = null;

// --- Lobby flow ---
btnCreate.onclick = async () => {
  const res = await fetch("/create", { method: "POST" });
  const j = await res.json();
  location.search = `?game=${j.game_id}`;
};

// --- Game init ---
const gameId = getParam("game");
if (gameId) {
  lobby.style.display = "none";
  gameDiv.style.display = "block";
  ws = new WebSocket(`ws://${location.host}/ws/${gameId}`);
  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "state") updateState(msg);
    if (msg.type === "forfeit_win") alert("Opponent left – you win!");
  };
}

// --- State sync & rendering ---
function updateState(state) {
  turnEl.textContent = "Turn: " + state.turn;
  const me = state.turn; // using turn as “you” for demo
  actionsEl.textContent = "Actions: " + state.players[me].actions_left;
  basesEl.textContent = "Bases: " + state.players[me].bases_remaining;
  renderBoard(state.board);
  renderHand(state.players[me].hand);
}

function renderBoard(tiles) {
  svg.innerHTML = "";
  for (let t of tiles) {
    const { q, r, owner, unit, health } = t;
    const { x, y } = axialToPixel(q, r);
    const poly = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "polygon"
    );
    poly.setAttribute("points", hexPolygon(x, y));
    poly.classList.add("hex");
    if (owner) poly.classList.add(`owned-${owner}`);
    poly.dataset.q = q;
    poly.dataset.r = r;
    svg.appendChild(poly);
    // click handler
    poly.onclick = () => {
      if (!selectedCard) return;
      ws.send(
        JSON.stringify({
          action: "play_card",
          card_type: selectedCard,
          target: { q, r },
        })
      );
    };
    // unit icon
    if (unit) {
      const txt = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "text"
      );
      txt.setAttribute("x", x);
      txt.setAttribute("y", y + 5);
      txt.setAttribute("text-anchor", "middle");
      txt.textContent = unit[0].toUpperCase() + health;
      svg.appendChild(txt);
    }
  }
}

function renderHand(hand) {
  handDiv.innerHTML = "";
  for (let c of hand) {
    const btn = document.createElement("div");
    btn.className = "card";
    btn.textContent = `${c} (${CARD_COST[c]})`;
    btn.onclick = () => {
      qsa(".card").forEach((el) => el.classList.remove("selected"));
      btn.classList.add("selected");
      selectedCard = c;
    };
    handDiv.appendChild(btn);
  }
}

// TODO: Pull from backend constants
const CARD_COST = {
  create_base: 3,
  create_ship: 2,
  move: 1,
  attack: 1,
};

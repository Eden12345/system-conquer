import random
from typing import List
from .constants import CARD_COUNTS, CARD_COST

class Card:
    def __init__(self, type: str):
        self.type = type
        self.cost = CARD_COST[type]

class PlayerState:
    def __init__(self):
        deck = []
        for t, count in CARD_COUNTS.items():
            deck += [Card(t) for _ in range(count)]
        random.shuffle(deck)
        self.deck: List[Card] = deck
        self.hand: List[Card] = []
        self.discard: List[Card] = []
        self.actions_left: int = 3
        self.bases_remaining: int = 0

    def draw_start(self):
        # draw up to 4, reshuffle if needed
        while len(self.hand) < 4 and self.deck:
            self.hand.append(self.deck.pop())
        if not self.deck:
            random.shuffle(self.discard)
            self.deck, self.discard = self.discard, []
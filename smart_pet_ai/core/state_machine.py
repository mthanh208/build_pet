# -*- coding: utf-8 -*-
import json, os

try:
    from transitions import Machine, State
    HAS_TRANSITIONS = True
except ImportError:
    HAS_TRANSITIONS = False

STATES = ['idle', 'listening', 'parsing', 'retrieving', 'reasoning', 'verifying', 'synthesizing', 'responding', 'dreaming', 'learning', 'confused', 'empathetic', 'curious']

TRANSITIONS = [
    {'trigger': 'receive_input', 'source': 'idle', 'dest': 'listening'},
    {'trigger': 'receive_input', 'source': 'listening', 'dest': 'listening'},
    {'trigger': 'start_parsing', 'source': ['listening', 'idle'], 'dest': 'parsing'},
    {'trigger': 'start_retrieval', 'source': 'parsing', 'dest': 'retrieving'},
    {'trigger': 'start_reasoning', 'source': 'retrieving', 'dest': 'reasoning'},
    {'trigger': 'start_reasoning', 'source': 'parsing', 'dest': 'reasoning'},
    {'trigger': 'start_verification', 'source': 'reasoning', 'dest': 'verifying'},
    {'trigger': 'verify_pass', 'source': 'verifying', 'dest': 'synthesizing'},
    {'trigger': 'verify_fail', 'source': 'verifying', 'dest': 'confused'},
    {'trigger': 'start_synthesis', 'source': ['reasoning', 'confused'], 'dest': 'synthesizing'},
    {'trigger': 'respond', 'source': 'synthesizing', 'dest': 'responding'},
    {'trigger': 'finish', 'source': 'responding', 'dest': 'idle'},
    {'trigger': 'go_idle', 'source': '*', 'dest': 'idle'},
    {'trigger': 'go_curious', 'source': '*', 'dest': 'curious'},
    {'trigger': 'go_empathetic', 'source': '*', 'dest': 'empathetic'},
    {'trigger': 'start_dreaming', 'source': 'idle', 'dest': 'dreaming'},
    {'trigger': 'stop_dreaming', 'source': 'dreaming', 'dest': 'idle'},
    {'trigger': 'start_learning', 'source': 'idle', 'dest': 'learning'},
    {'trigger': 'stop_learning', 'source': 'learning', 'dest': 'idle'},
]

class PetStateMachine:
    def __init__(self, save_path=None):
        self.save_path = save_path
        self.state_history = []
        self.transition_count = 0

        if HAS_TRANSITIONS:
            self.machine = Machine(model=self, states=STATES, transitions=TRANSITIONS, initial='idle')
        else:
            self._state = 'idle'
            self._transitions_map = {}
            for t in TRANSITIONS:
                src = t['source'] if isinstance(t['source'], list) else [t['source']]
                for s in src:
                    key = (s, t['trigger'])
                    self._transitions_map[key] = t['dest']

    def trigger(self, event):
        if HAS_TRANSITIONS:
            try: getattr(self, event)()
            except: pass
        else:
            key = (self._state, event)
            if key in self._transitions_map:
                old = self._state
                self._state = self._transitions_map[key]
                self.state_history.append((old, self._state, event))
                self.transition_count += 1
                if len(self.state_history) > 50: self.state_history = self.state_history[-25:]

    def get_state(self):
        if HAS_TRANSITIONS: return self.state
        return self._state

    def is_busy(self):
        return self.get_state() not in ('idle', 'dreaming')

    def stats(self):
        return {"current_state": self.get_state(), "transition_count": self.transition_count, "available": HAS_TRANSITIONS}

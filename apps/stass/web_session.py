"""Short-lived one-time pairing codes and browser-only sessions."""
import hashlib
import secrets
import threading
import time


class WebSessions:
    def __init__(self):
        self.lock = threading.Lock()
        self.codes = {}
        self.sessions = {}
        self.attempts = {}

    @staticmethod
    def key(value):
        return hashlib.sha256(value.encode()).hexdigest()

    def issue(self):
        with self.lock:
            self.codes = {k:v for k,v in self.codes.items() if v > time.monotonic()}
            if len(self.codes) >= 10:
                raise ValueError('Too many outstanding pairing codes')
            code = secrets.token_urlsafe(18)
            self.codes[self.key(code)] = time.monotonic() + 300
            return code

    def exchange(self, code, peer):
        with self.lock:
            now = time.monotonic()
            self.attempts = {k:v for k,v in self.attempts.items() if v[1] > now}
            count, until = self.attempts.get(peer, (0, now+60))
            if count >= 10:
                raise ValueError('Too many pairing attempts; wait one minute')
            self.attempts[peer] = (count+1, until)
            expires = self.codes.pop(self.key(code), 0)
            if expires <= now:
                raise ValueError('Pairing code is invalid or expired')
            self.sessions = {k:v for k,v in self.sessions.items() if v > now}
            if len(self.sessions) >= 100:
                raise ValueError('Too many browser sessions')
            token = secrets.token_urlsafe(48)
            self.sessions[self.key(token)] = now + 12*3600
            return token

    def valid(self, token):
        with self.lock:
            return bool(token) and self.sessions.get(self.key(token), 0) > time.monotonic()

    def revoke(self, token):
        with self.lock:
            self.sessions.pop(self.key(token), None)

# Live racing game

This is a simple 2d racing game where players have to write software for autonomous car to complete laps around a racetrack as quickly and reliably as possible.
The game is supposed to be run on a server, with clients interacting via http requests (see `client.py` for the format of the requests).
A visualization tool is provided (`visualizer.py`) which connects to the server and displays the game state.

The python dependencies are managed with pdm (install that first: `python3 -m pip install pdm`). To install dependencies run 

```
pdm sync
```

And to run any of (`client.py`, `server.py`, `visualizer.py`) run

```
pdm run python <script>
```

Alternatively you can just install all dependencies using pip and it should also work.

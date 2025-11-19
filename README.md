# Cheesecake — Discord Bot & Mini Games
A multi-purpose Discord bot and small local mini-game project.

## Repositories / Layout
- Bot core and cogs: see [main.py](main.py) and the [cogs/](cogs/) folder.
- Mini-game: see [bake-with-cheesecake/README.md](bake-with-cheesecake/README.md) and [bake-with-cheesecake/src/main.py](bake-with-cheesecake/src/main.py).

## Quick start (bot)
1. Create a Python 3.12 venv and install dependencies:
   ```
   pip install -r requirements.txt
   ```
   See [requirements.txt](requirements.txt).

2. Add your bot token to a `.env` file:
   ```
   DISCORD_TOKEN=your_token_here
   ```
   The bot loads the token from the environment in [main.py](main.py).

3. Run the bot:
   ```
   python main.py
   ```

Notes:
- The main bot entrypoint is [main.py](main.py).
- Message-response logic uses [`ResponseHandler.get_response`](cogs/responsehandler.py).
- Cogs are auto-loaded from the [cogs/](cogs/) folder on startup.

## Bake-with-Cheesecake mini-game
- Local mini-game lives under [bake-with-cheesecake/](bake-with-cheesecake/).
- Game entrypoint: [bake-with-cheesecake/src/main.py](bake-with-cheesecake/src/main.py).
- Leaderboard class: [`Leaderboard`](bake-with-cheesecake/src/leaderboard.py).
- See [bake-with-cheesecake/README.md](bake-with-cheesecake/README.md) for local gameplay instructions.

## Development
- Add or edit cogs in [cogs/](cogs/). Each cog exposes an async `setup` to register itself with the bot (see examples in the repo).
- Database helpers are defined per-cog (many use MySQL/pymysql or mysql.connector). Check cog files such as [cogs/starboard.py](cogs/starboard.py) and [cogs/responsehandler.py](cogs/responsehandler.py) for DB examples.
- UI/interaction code uses discord.py view/buttons patterns (see [cogs/giveaway.py](cogs/giveaway.py) and [cogs/emergancy_commissions.py](cogs/emergancy_commissions.py)).

## Security & best practices
- Never commit tokens. Use `.env` and ensure `.gitignore` covers env files (see [.gitignore](.gitignore)).
- Remove or rotate any hardcoded tokens found in the workspace (e.g., `invite.py` currently contains a token string — rotate it and move to environment variables).

## Contributing
- Fork, create a branch, run tests/manual checks, submit a PR.
- Keep secrets out of commits.

## Useful files
- [main.py](main.py)
- [requirements.txt](requirements.txt)
- [bake-with-cheesecake/src/main.py](bake-with-cheesecake/src/main.py)
- [bake-with-cheesecake/src/leaderboard.py](bake-with-cheesecake/src/leaderboard.py)
- [`ResponseHandler.get_response`](cogs/responsehandler.py)
- [bake-with-cheesecake/README.md](bake-with-cheesecake/README.md)

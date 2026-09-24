"""Route modules, collected into one router the app can include.

Adding a new resource means writing its module and appending one line here.
"""

from fastapi import APIRouter

from app.api.routes import players, teams

api_router = APIRouter()
api_router.include_router(teams.router)
api_router.include_router(players.router)

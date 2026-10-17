"""The Campus Customs agent team. One file per role; team.py runs them."""

from . import accounting, boss, customer_service, facilities, inventory

TEAM = {p.PROFILE.id: p.PROFILE for p in (boss, inventory, accounting, facilities, customer_service)}

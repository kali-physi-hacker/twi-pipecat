import csv
import random
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

from .transactions import NAME_PHONE_MAP, NAMES


@dataclass(frozen=True)
class User:
    user_id: str
    phone_number: str
    full_name: str
    account_type: Literal["Savings", "Checkings"]
    balance_ghs: Decimal


def _build_users() -> tuple[User, ...]:
    rng = random.Random(20261123)
    users = tuple(
        User(
            user_id=f"{index:03d}",
            phone_number=f"0{NAME_PHONE_MAP[name]:09d}",
            full_name=name,
            account_type=rng.choice(("Savings", "Checkings")),
            balance_ghs=Decimal(rng.randrange(0, 5_000_001)).scaleb(-2),
        )
        for index, name in enumerate(NAMES, start=1)
    )

    csv_path = Path(__file__).with_name("accounts.csv")
    fields = ("user_id", "phone_number", "full_name", "account_type", "balance_ghs")

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        for user in users:
            writer.writerow(
                {
                    "user_id": user.user_id,
                    "phone_number": user.phone_number,
                    "full_name": user.full_name,
                    "account_type": user.account_type,
                    "balance_ghs": format(user.balance_ghs, ".2f"),
                }
            )

    return users


USERS = _build_users()

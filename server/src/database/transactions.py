import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone


@dataclass(frozen=True)
class Transaction:
    transaction_id: str
    phone_number_from: int
    phone_number_to: int
    person_name_from: str
    person_name_to: str
    transaction_amount_in_cedi: int
    date_created: datetime


NAMES = (
    "Ama Mensah",
    "Kwame Asare",
    "Akosua Boateng",
    "Kofi Owusu",
    "Abena Sarpong",
    "Yaw Mensah",
    "Efua Addo",
    "Kojo Agyeman",
    "Mariam Issah",
    "Nana Yeboah",
    "Adwoa Frimpong",
    "Ibrahim Osman",
    "Selorm Kpodo",
    "Esi Ofori",
    "Samuel Quaye",
    "Felicity Appiah",
    "Emmanuel Tetteh",
    "Comfort Darko",
    "Josephine Nartey",
    "Rashid Yakubu",
)

PHONE_PREFIXES = ("020", "023", "024", "025", "027", "050", "053", "054", "055", "059")


NAME_PHONE_MAP = {
    name: int(rng_phone)
    for name, rng_phone in zip(
        NAMES,
        (
            "0241234567",
            "0552345678",
            "0203456789",
            "0504567890",
            "0275678901",
            "0596789012",
            "0547890123",
            "0238901234",
            "0539012345",
            "0251123456",
            "0242234567",
            "0553345678",
            "0204456789",
            "0505567890",
            "0276678901",
            "0597789012",
            "0548890123",
            "0239901234",
            "0531012345",
            "0252123456",
        ),
        strict=True,
    )
}


def _ghana_phone(rng: random.Random) -> int:
    phone = rng.choice(PHONE_PREFIXES) + "".join(str(rng.randint(0, 9)) for _ in range(7))
    return int(phone.lstrip("0"))


def _build_transactions(count: int = 2000) -> tuple[Transaction, ...]:
    rng = random.Random(20261122)
    start = datetime(2024, 1, 1, tzinfo=UTC)
    span = timedelta(days=980)
    rows: list[Transaction] = []

    for _ in range(count):
        from_name = rng.choice(NAMES)
        to_name = rng.choice([name for name in NAMES if name != from_name])
        phone_from = NAME_PHONE_MAP[from_name]
        phone_to = NAME_PHONE_MAP[to_name]
        amount = rng.choice(
            tuple(range(10, 101, 5))
            + tuple(range(125, 501, 25))
            + (550, 600, 750, 900, 1000, 1250, 1500, 2000)
        )
        date_created = start + timedelta(
            days=rng.randint(0, span.days),
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )
        transaction_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{phone_from}-{phone_to}-{amount}-{date_created.isoformat()}",
            )
        )
        rows.append(
            Transaction(
                transaction_id=transaction_id,
                phone_number_from=phone_from,
                phone_number_to=phone_to,
                person_name_from=from_name,
                person_name_to=to_name,
                transaction_amount_in_cedi=amount,
                date_created=date_created,
            )
        )

    return tuple(sorted(rows, key=lambda row: row.date_created))


TRANSACTIONS = _build_transactions()

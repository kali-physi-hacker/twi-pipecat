import re

from pipecat.services.llm_service import FunctionCallParams

from dataclasses import dataclass


@dataclass
class Transaction:
    amount: int
    recipient: str
    status: str


def extract_amount(params: FunctionCallParams, text: str) -> str | None:
    """Extract the amount of a failed transfer from a Twi text using a regrex text search.

    Args:
        text: The user's request that may or may not contain a cedis amount. e.g. "Hello. Me transfer no antumi anyɛ yiye. Mede cedis 50 kɔmaa 0244624309 na sika no amma?".
    """
    match = re.search(r"\b(\d+)\s*(?:cedis?|ghc)?\b", text.lower())
    return match.group(1) if match else None


# extract a phone number out of a text using regrex
def extract_phone_number(text: str) -> str | None:
    match = re.search(r"\b0\d{9}\b", text)
    return match.group(0) if match else None


# can be an api call
def lookup_transaction(database, amount: str, recipient: str) -> Transaction | None:
    return database.get((amount, recipient))


async def find_transaction(
    params: FunctionCallParams, transcript: str
) -> tuple[Transaction | None, str, str]:
    statuses = ["pending", "completed", "failed"]
    database = {
        (str(amount), recipient): Transaction(
            amount=amount,
            recipient=recipient,
            status=statuses[index % len(statuses)],
        )
        for index, (amount, recipient) in enumerate(
            [
                (10, "0240000001"),
                (15, "0240000002"),
                (20, "0240000003"),
                (25, "0240000004"),
                (30, "0240000005"),
                (35, "0240000006"),
                (40, "0240000007"),
                (45, "0240000008"),
                (50, "0244624309"),
                (55, "0240000010"),
                (60, "0240000011"),
                (65, "0240000012"),
                (70, "0240000013"),
                (75, "0240000014"),
                (80, "0240000015"),
                (85, "0240000016"),
                (90, "0240000017"),
                (95, "0240000018"),
                (100, "0240000019"),
                (105, "0240000020"),
                (110, "0240000021"),
                (115, "0240000022"),
                (120, "0240000023"),
                (125, "0240000024"),
                (130, "0240000025"),
                (135, "0240000026"),
                (140, "0240000027"),
                (145, "0240000028"),
                (150, "0240000029"),
                (155, "0240000030"),
                (160, "0240000031"),
                (165, "0240000032"),
                (170, "0240000033"),
                (175, "0240000034"),
                (180, "0240000035"),
                (185, "0240000036"),
                (190, "0240000037"),
                (195, "0240000038"),
                (200, "0240000039"),
                (205, "0240000040"),
                (210, "0240000041"),
                (215, "0240000042"),
                (220, "0240000043"),
                (225, "0240000044"),
                (230, "0240000045"),
                (235, "0240000046"),
                (240, "0240000047"),
                (245, "0240000048"),
                (250, "0240000049"),
                (255, "0240000050"),
            ]
        )
    }
    amount = extract_amount(transcript)
    recipient = extract_phone_number(transcript)
    if amount is None or recipient is None:
        return {
            "status": "missing_information",
            "amount": amount,
            "recipient": recipient,
            "message": "Ask the user for the missing transfer amount or recipient phone number.",
        }
    transaction = lookup_transaction(database, amount, recipient)
    if transaction is None:
        return {
            "status": "not_found",
            "amount": amount,
            "recipient": recipient,
            "message": "Transaction was not found. Repeat the amount and recipient phone number and whether they are what the user mentioned.",
        }
    return {
        "status": "found",
        "amount": amount,
        "recipient": recipient,
        "transaction_status": transaction.status,
        "message": "Tell the user that the transaction was found and in what status it is.",
    }


def process_failed_transfer(transcript: str) -> dict:
    lower_text = transcript.lower()

    if "pin" in lower_text:
        return {
            "response": "I cannot collect or repeat a PIN. I am transferring you to an agent.",
            "action": "escalate",
        }

    if "agent" in lower_text:
        return {
            "response": "I am transferring you to an agent.",
            "action": "escalate",
        }

    transaction, amount, recipient = find_transaction(transcript, database)

    # No transaction matches the speaker's description
    while transaction is None:
        transcript = input(
            f"I could not find a {amount} cedi transfer to {recipient}. Could you verify that the information is accurate?"
        )
        # if the user confirms that it was a mistake
        if transcript == "NO":
            return {
                "response": "I could not find that transaction. I am transferring you to an agent.",
                "action": "escalate",
            }
        transaction, amount, recipient = find_transaction(transcript, database)

    return {
        "response": (
            f"I found the {amount} cedi transfer to {recipient}. "
            f"It is currently {transaction.status}. "
            "I will submit a reversal request for human approval."
        ),
        "action": "request_reversal_approval",
        "amount": amount,
        "recipient": recipient,
        "status": transaction.status,
    }

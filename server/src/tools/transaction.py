import re
from datetime import UTC, datetime, timezone

from pipecat.services.llm_service import FunctionCallParams

from src.database import TRANSACTIONS


def extract_amount(text: str) -> str | None:
    """Extract a cedi amount from a transfer description."""

    def normalize(value: str) -> str:
        if "." not in value:
            return value
        return value.rstrip("0").rstrip(".")

    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:cedis?|ghs?|ghc)\b", text.lower())
    if match:
        return normalize(match.group(1))

    match = re.search(r"(?:cedis?|ghs?|ghc)\s*(\d+(?:\.\d+)?)\b", text.lower())
    if match:
        return normalize(match.group(1))
    return None


def extract_phone_number(text: str) -> str | None:
    """Extract a Ghanaian local phone number without its leading zero."""
    match = re.search(r"\b0(\d{9})\b", text)
    if match:
        return match.group(1)

    match = re.search(r"\b(\d{9})\b", text)
    return match.group(1) if match else None


async def find_transaction(
    params: FunctionCallParams,
    transcript: str,
) -> dict:
    """Find a transaction from an amount and recipient phone number.

    Args:
        transcript: A description containing the transfer amount and recipient phone number.
    """
    amount = extract_amount(transcript)
    recipient = extract_phone_number(transcript)

    if amount is None or recipient is None:
        result = {
            "status": "missing_information",
            "amount": amount,
            "recipient": recipient,
            "message": "Ask the user for the missing transfer amount and recipient phone number.",
        }
        await params.result_callback(result)
        return result

    recipient_value = int(recipient)
    amount_value = int(float(amount))
    transaction = next(
        (
            row
            for row in TRANSACTIONS
            if row.phone_number_to == recipient_value
            and row.transaction_amount_in_cedi == amount_value
        ),
        None,
    )

    if transaction is None:
        result = {
            "status": "not_found",
            "amount": amount,
            "recipient": recipient,
            "message": "No matching transaction was found. Ask the user to confirm the amount and recipient phone number.",
        }
        await params.result_callback(result)
        return result

    result = {
        "status": "found",
        "transaction_id": transaction.transaction_id,
        "phone_number_from": transaction.phone_number_from,
        "phone_number_to": transaction.phone_number_to,
        "person_name_from": transaction.person_name_from,
        "person_name_to": transaction.person_name_to,
        "transaction_amount_in_cedi": transaction.transaction_amount_in_cedi,
        "date_created": transaction.date_created.isoformat(),
        "transfer_status": transaction.status,
        "message": "Tell the user that the transaction was found.",
    }
    await params.result_callback(result)
    return result


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None

    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


async def get_sum(
    params: FunctionCallParams,
    phone_number: str | int | None = None,
    time_from: str | None = None,
    time_to: str | None = None,
) -> dict:
    """Get the gross transaction total for a phone number in an optional time period.

    Args:
        phone_number: Ghanaian local or international-format phone number.
        time_from: Optional inclusive ISO timestamp for the start of the period.
        time_to: Optional inclusive ISO timestamp for the end of the period.
    """
    if phone_number is None or not str(phone_number).strip():
        result = {
            "status": "missing_information",
            "message": "Please provide the person's Ghanaian phone number.",
        }
        await params.result_callback(result)
        return result

    raw_phone = re.sub(r"\D", "", str(phone_number).strip())
    if raw_phone.startswith("233") and len(raw_phone) == 12:
        raw_phone = "0" + raw_phone[3:]

    if len(raw_phone) == 10 and raw_phone.startswith("0"):
        identifier_phone = int(raw_phone[1:])
    elif len(raw_phone) == 9:
        identifier_phone = int(raw_phone)
    else:
        result = {
            "status": "invalid_phone_number",
            "phone_number": phone_number,
            "message": "Please provide a valid Ghanaian local or international phone number.",
        }
        await params.result_callback(result)
        return result

    from_timestamp = _parse_timestamp(time_from)
    to_timestamp = _parse_timestamp(time_to)

    if from_timestamp and to_timestamp and from_timestamp > to_timestamp:
        result = {
            "status": "invalid_time_period",
            "message": "The starting time must be before or equal to the end time.",
        }
        await params.result_callback(result)
        return result

    person_rows = [
        row
        for row in TRANSACTIONS
        if row.phone_number_from == identifier_phone or row.phone_number_to == identifier_phone
    ]

    if not person_rows:
        result = {
            "status": "not_found",
            "phone_number": phone_number,
            "message": "There is no transaction record for this phone number.",
        }
        await params.result_callback(result)
        return result

    total_received = 0
    total_transferred = 0
    matching_rows = []

    for row in person_rows:
        if from_timestamp and row.date_created < from_timestamp:
            continue
        if to_timestamp and row.date_created > to_timestamp:
            continue

        matching_rows.append(row)
        is_sender = row.phone_number_from == identifier_phone
        is_receiver = row.phone_number_to == identifier_phone
        if is_sender:
            total_transferred += row.transaction_amount_in_cedi
        if is_receiver:
            total_received += row.transaction_amount_in_cedi

    result = {
        "status": "found",
        "phone_number": phone_number,
        "time_from": time_from,
        "time_to": time_to,
        "transaction_count": len(matching_rows),
        "total_amount_received_in_cedi": total_received,
        "total_amount_transferred_in_cedi": total_transferred,
        "total_amount_in_cedi": total_received + total_transferred,
    }
    await params.result_callback(result)
    return result

import re

from pipecat.services.llm_service import FunctionCallParams

from src.database.accounts import USERS, User


def _normalize_user_id(user_id: str | int) -> str | None:
    value = str(user_id).strip()
    if not value.isascii() or not value.isdigit() or len(value) > 3:
        return None
    return value.zfill(3)


def _normalize_phone_number(phone_number: str) -> str | None:
    digits = re.sub(r"\D", "", phone_number)
    if digits.startswith("233") and len(digits) == 12:
        digits = "0" + digits[3:]
    elif len(digits) == 9:
        digits = "0" + digits

    if len(digits) == 10 and digits.startswith("0"):
        return digits
    return None


def _normalize_name(full_name: str) -> str:
    return " ".join(full_name.split()).casefold()


def _find_user(user_id: str | int) -> User | None:
    normalized_user_id = _normalize_user_id(user_id)
    if normalized_user_id is None:
        return None
    return next((user for user in USERS if user.user_id == normalized_user_id), None)


async def _return_result(params: FunctionCallParams, result: dict[str, str]) -> dict[str, str]:
    await params.result_callback(result)
    return result


async def get_account_balance(
    params: FunctionCallParams,
    user_id: str | int,
) -> dict[str, str]:
    """Look up a user's current account balance in Ghanaian cedis by user ID.

    Args:
        user_id: The user's three-digit ID.
    """
    user = _find_user(user_id)
    if user is None:
        return await _return_result(
            params,
            {
                "status": "not_found",
                "user_id": str(user_id),
                "message": "No account was found for that user ID. Ask the user to confirm it.",
            },
        )

    return await _return_result(
        params,
        {
            "status": "found",
            "user_id": user.user_id,
            "balance_ghs": format(user.balance_ghs, ".2f"),
            "currency": "GHS",
            "message": "Tell the user their current account balance in Ghanaian cedis.",
        },
    )


async def get_account_type(
    params: FunctionCallParams,
    user_id: str | int,
) -> dict[str, str]:
    """Look up a user's account type by user ID.

    Args:
        user_id: The user's three-digit ID.
    """
    user = _find_user(user_id)
    if user is None:
        return await _return_result(
            params,
            {
                "status": "not_found",
                "user_id": str(user_id),
                "message": "No account was found for that user ID. Ask the user to confirm it.",
            },
        )

    return await _return_result(
        params,
        {
            "status": "found",
            "user_id": user.user_id,
            "account_type": user.account_type,
            "message": "Tell the user their account type.",
        },
    )


async def find_user_id(
    params: FunctionCallParams,
    phone_number: str,
    full_name: str,
) -> dict[str, str]:
    """Find a user's ID using their Ghanaian phone number and full name.

    Args:
        phone_number: Ghanaian phone number in local or +233 international format.
        full_name: The user's full name.
    """
    normalized_phone = _normalize_phone_number(phone_number)
    if normalized_phone is None:
        return await _return_result(
            params,
            {
                "status": "invalid_phone_number",
                "message": "Ask for a valid Ghanaian phone number, such as 0241234567 or +233241234567.",
            },
        )

    normalized_name = _normalize_name(full_name)
    if not normalized_name:
        return await _return_result(
            params,
            {
                "status": "missing_information",
                "message": "Ask the user for their full name.",
            },
        )

    user = next(
        (
            candidate
            for candidate in USERS
            if candidate.phone_number == normalized_phone
            and _normalize_name(candidate.full_name) == normalized_name
        ),
        None,
    )
    if user is None:
        return await _return_result(
            params,
            {
                "status": "not_found",
                "message": "No account matched both details. Ask the user to verify their full name and phone number.",
            },
        )

    return await _return_result(
        params,
        {
            "status": "found",
            "user_id": user.user_id,
            "message": "Provide the user's ID only after both their full name and phone number matched.",
        },
    )

"""Response utilities for standardized error and success responses."""

from typing import Any


def create_error_response(
    error_type: str,
    message: str,
    details: str | None = None,
    **additional_fields: Any,
) -> dict[str, Any]:
    """Create standardized error response.

    Args:
        error_type (str): Short error type identifier
        message (str): Detailed error message
        details (str, optional): Additional context or help information
        **additional_fields: Any additional fields to include in response

    Returns:
        dict[str, Any]: Standardized error response dictionary

    Example:
        >>> create_error_response(
        ...     'Invalid format',
        ...     'Expected "type:key=value" format',
        ...     'Use format like "works_at:position=developer"'
        ... )
        {
            'success': False,
            'error': 'Invalid format',
            'message': 'Expected "type:key=value" format',
            'details': 'Use format like "works_at:position=developer"'
        }
    """
    response = {
        'success': False,
        'error': error_type,
        'message': message,
    }

    if details is not None:
        response['details'] = details

    # Add any additional fields
    response.update(additional_fields)

    return response


def create_success_response(**fields: Any) -> dict[str, Any]:
    """Create standardized success response.

    Args:
        **fields: Any fields to include in the success response

    Returns:
        dict[str, Any]: Standardized success response dictionary

    Example:
        >>> create_success_response(created=5, entities=['user1', 'user2'])
        {
            'success': True,
            'created': 5,
            'entities': ['user1', 'user2']
        }
    """
    response = {'success': True}
    response.update(fields)
    return response

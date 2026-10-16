import re

# Kenyan mobile numbers: 7XXXXXXXX or 1XXXXXXXX after the country code.
_LOCAL_PATTERN = re.compile(r'^[17]\d{8}$')


def normalize_msisdn(raw):
    """Return a Kenyan number as 2547XXXXXXXX / 2541XXXXXXXX, or None if invalid.

    Accepts 0712345678, 712345678, 254712345678, +254712345678 and spaced variants.
    """
    if raw is None:
        return None
    digits = re.sub(r'[\s\-]', '', str(raw)).lstrip('+')
    if not digits.isdigit():
        return None
    if digits.startswith('254'):
        local = digits[3:]
    elif digits.startswith('0'):
        local = digits[1:]
    else:
        local = digits
    if not _LOCAL_PATTERN.match(local):
        return None
    return f'254{local}'


def display_msisdn(msisdn):
    """2547XXXXXXXX -> 07XXXXXXXX for showing on a USSD screen."""
    if msisdn and msisdn.startswith('254') and len(msisdn) == 12:
        return f'0{msisdn[3:]}'
    return msisdn

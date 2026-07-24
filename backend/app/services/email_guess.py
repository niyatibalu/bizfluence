from app.schemas import EmailGuessOut


COMMON_PATTERNS = [
    ("{first}.{last}", "high"),
    ("{first}{last}", "medium"),
    ("{f}{last}", "medium"),
    ("{first}_{last}", "low"),
    ("{first}", "low"),
]


def guess_corporate_email(first_name: str, last_name: str, domain: str) -> EmailGuessOut:
    first = "".join(c for c in first_name.lower().strip() if c.isalpha())
    last = "".join(c for c in last_name.lower().strip() if c.isalpha())
    domain = domain.lower().strip().removeprefix("https://").removeprefix("http://").removeprefix("www.")
    domain = domain.split("/")[0]

    if not first or not domain:
        return EmailGuessOut(
            email="",
            confidence="low",
            pattern="",
            alternatives=[],
        )

    emails: list[tuple[str, str, str]] = []
    for pattern, confidence in COMMON_PATTERNS:
        local = pattern.format(first=first, last=last or first, f=first[0])
        emails.append((f"{local}@{domain}", confidence, pattern))

    primary_email, primary_conf, primary_pat = emails[0]
    return EmailGuessOut(
        email=primary_email,
        confidence=primary_conf,  # type: ignore[arg-type]
        pattern=primary_pat,
        alternatives=[e[0] for e in emails[1:]],
    )

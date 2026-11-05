"""Country names (German and English) to the 2-letter codes the FundraisingBox API wants."""

_NAMES: dict[str, tuple[str, ...]] = {
    "DE": ("deutschland", "germany", "bundesrepublik deutschland"),
    "AT": ("österreich", "oesterreich", "austria"),
    "CH": ("schweiz", "switzerland", "suisse", "svizzera"),
    "LI": ("liechtenstein",),
    "LU": ("luxemburg", "luxembourg"),
    "NL": ("niederlande", "netherlands", "holland", "nederland"),
    "BE": ("belgien", "belgium", "belgique"),
    "FR": ("frankreich", "france"),
    "IT": ("italien", "italy", "italia"),
    "ES": ("spanien", "spain", "españa"),
    "PT": ("portugal",),
    "GB": ("vereinigtes königreich", "united kingdom", "uk", "großbritannien", "great britain"),
    "IE": ("irland", "ireland"),
    "DK": ("dänemark", "denmark"),
    "SE": ("schweden", "sweden"),
    "NO": ("norwegen", "norway"),
    "FI": ("finnland", "finland"),
    "PL": ("polen", "poland"),
    "CZ": ("tschechien", "czech republic", "czechia"),
    "SK": ("slowakei", "slovakia"),
    "HU": ("ungarn", "hungary"),
    "SI": ("slowenien", "slovenia"),
    "HR": ("kroatien", "croatia"),
    "RO": ("rumänien", "romania"),
    "BG": ("bulgarien", "bulgaria"),
    "GR": ("griechenland", "greece"),
    "TR": ("türkei", "turkey"),
    "US": ("vereinigte staaten", "usa", "united states", "united states of america"),
    "CA": ("kanada", "canada"),
    "AU": ("australien", "australia"),
    "UA": ("ukraine",),
    "EE": ("estland", "estonia"),
    "LV": ("lettland", "latvia"),
    "LT": ("litauen", "lithuania"),
}

_BY_NAME = {name: code for code, names in _NAMES.items() for name in names}


def country_code(value: str) -> str | None:
    """A 2-letter code for the country text, or None when empty or not recognised."""
    text = value.strip().lower()
    if not text:
        return None
    if len(text) == 2 and text.isalpha():
        return text.upper()
    return _BY_NAME.get(text)

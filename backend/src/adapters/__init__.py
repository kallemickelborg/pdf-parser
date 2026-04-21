"""Template-specific extraction adapters for PDF invoices.

The public surface of this package is `ALL_ADAPTERS` plus the `InvoiceAdapter`
protocol. The pipeline orchestrates them; adapters only know how to score
their confidence for a given piece of text and extract what they can.
"""

from src.adapters.base import ExtractionContext, InvoiceAdapter
from src.adapters.bilingual_de_en import BilingualGermanEnglishAdapter
from src.adapters.crayon_da import CrayonAdapter
from src.adapters.danish import DanishAdapter
from src.adapters.english import EnglishAdapter
from src.adapters.generic import GenericKeywordAdapter
from src.adapters.kmd_da import KMDAdapter
from src.adapters.microsoft_dk import MicrosoftDKAdapter
from src.adapters.sap_da import SAPAdapter

# Order matters for tie-breaks (Python's sort is stable). Vendor-specific
# adapters come first so they win when both a vendor-specific adapter and
# the generic DanishAdapter return a confidence of 1.0. Generic language
# adapters come next, and GenericKeywordAdapter stays last as the universal
# fallback.
ALL_ADAPTERS: tuple[InvoiceAdapter, ...] = (
    SAPAdapter(),
    MicrosoftDKAdapter(),
    KMDAdapter(),
    CrayonAdapter(),
    DanishAdapter(),
    EnglishAdapter(),
    BilingualGermanEnglishAdapter(),
    GenericKeywordAdapter(),
)

__all__ = [
    "ALL_ADAPTERS",
    "BilingualGermanEnglishAdapter",
    "CrayonAdapter",
    "DanishAdapter",
    "EnglishAdapter",
    "ExtractionContext",
    "GenericKeywordAdapter",
    "InvoiceAdapter",
    "KMDAdapter",
    "MicrosoftDKAdapter",
    "SAPAdapter",
]

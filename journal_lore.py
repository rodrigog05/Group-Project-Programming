"""Short, sourced Lisbon history bundled for offline journal reading.

References were checked against the named heritage, tourism, conservation
and river authorities. Opening a reference is optional; importing this
module performs no network requests.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    title: str
    url: str


@dataclass(frozen=True)
class LoreEntry:
    key: str
    title: str
    body: str
    sources: tuple


GAME_MAP_NOTE = (
    "The town's compact layout, tourism bonuses, recipes, prices and fares are fictional game rules. "
    "The historical and ecological notes below refer to the real Lisbon and Tejo."
)

UNESCO_BELEM = Source(
    "UNESCO · Monastery of the Hieronymites and Tower of Belém",
    "https://whc.unesco.org/en/list/263/",
)
CASTLE_WALLS = Source(
    "Castelo de São Jorge · The Walls",
    "https://castelodesaojorge.pt/en/castle/national-monument/the-walls/",
)
COMMERCE_SQUARE = Source(
    "Turismo de Portugal · Praça do Comércio",
    "https://www.visitportugal.com/en/NR/exeres/64BE2716-BB28-4041-8E05-594DF1BAAE95",
)
RIVER_BASIN = Source(
    "Albufeira Convention Commission · International Tagus river basin",
    "https://www.cadc-albufeira.eu/es/demarcaciones-internacionales/tajo/descripcion.html",
)
PORT_HISTORY = Source(
    "Port of Lisbon Authority · Historical background",
    "https://www.portodelisboa.pt/en/enquadramento-historico",
)
RESERVE_HISTORY = Source(
    "ICNF / Natural.PT · Tagus Estuary Reserve, 45th anniversary (2021)",
    "https://resources.natural.pt/uploads/additional-information/2021/08/03/15/mKIdNRCOtG526y6M.pdf",
)
ESTUARY_ECOLOGY = Source(
    "CCDR Lisboa e Vale do Tejo · Estuário do Tejo e Área de Reserva Natural",
    "https://www.ccdr-lvt.pt/wp-content/uploads/2022/03/EER_estuario-tejo-area-reserva-natural.pdf",
)


LANDMARK_LORE = (
    LoreEntry(
        "jeronimos",
        "Mosteiro dos Jerónimos",
        "King Manuel I commissioned this riverside monastery for the Hieronymite monks. "
        "UNESCO dates the beginning of construction to 1502. Its richly carved stonework "
        "is an example of Manueline architecture, and its surviving spaces include a "
        "sixteenth-century cloister. The monks offered spiritual support to seafarers "
        "departing Lisbon. The monastery and nearby Torre de Belém became a joint "
        "UNESCO World Heritage property in 1983. Their setting preserves an important "
        "connection between Belém and Portugal's maritime history.",
        (UNESCO_BELEM,),
    ),
    LoreEntry(
        "sao_jorge",
        "Castelo de São Jorge",
        "The castle belongs to a much older system of defenses overlooking the Tejo. "
        "An Arabic inscription records repairs to Lisbon's wall in 985, providing an "
        "early written record of the fortification. Afonso Henriques captured the "
        "fortress in 1147. The medieval citadel occupied the hilltop, while the city's "
        "walls continued down toward the waterfront. Its stonework therefore tells "
        "several chapters of Lisbon's history, including its Islamic and later "
        "Portuguese periods.",
        (CASTLE_WALLS,),
    ),
    LoreEntry(
        "belem_tower",
        "Torre de Belém",
        "Francisco de Arruda designed this early-sixteenth-century fortress beside "
        "the entrance to Lisbon's port. It helped defend the harbor and commemorated "
        "Vasco da Gama's expedition. Its carved decoration includes crosses of the "
        "Order of Christ, and its small watchtowers have ribbed domes reflecting "
        "Islamic architectural influences. The surrounding shoreline has changed "
        "through silting and land reclamation. Since 1983 the tower has shared UNESCO "
        "World Heritage status with Mosteiro dos Jerónimos.",
        (UNESCO_BELEM,),
    ),
    LoreEntry(
        "commerce_square",
        "Praça do Comércio",
        "Before the earthquake of 1755, the royal palace stood beside this riverfront "
        "space, known as Terreiro do Paço. The palace was destroyed, and the rebuilt "
        "Praça do Comércio expressed the importance of merchants and finance in the "
        "Pombaline reconstruction. The equestrian statue of José I, by Machado de "
        "Castro, was unveiled in 1775. The riverside dock also served as an arrival "
        "point for visiting monarchs and heads of state, linking the square to the Tejo.",
        (COMMERCE_SQUARE,),
    ),
)


TEJO_LORE = (
    LoreEntry(
        "tejo_journey",
        "From the Spanish mountains to Lisbon",
        "The Tejo begins in Spain's Sierra de Albarracín and travels more than "
        "1,000 kilometers toward the Atlantic. Part of its course forms the border "
        "between Spain and Portugal before the river continues through Portuguese "
        "territory to its estuary beside Lisbon. The Zêzere and Sorraia are among its "
        "Portuguese tributaries. The river and its drainage basin connect places far "
        "beyond the capital; the broad water shown in the town represents only its "
        "lower, estuarine landscape.",
        (RIVER_BASIN,),
    ),
    LoreEntry(
        "tejo_port",
        "A harbor shaped by centuries of trade",
        "The Tejo estuary's sheltered, navigable waters helped attract successive "
        "communities to Lisbon. The Port of Lisbon Authority traces this history "
        "through Phoenician, Roman, Islamic and later Portuguese periods. The harbor "
        "became a departure point for overseas voyages and a destination for "
        "long-distance commerce. Industrialization brought new logistical demands: "
        "major modernization works were inaugurated in 1887. The game’s factories "
        "and repair yard borrow this river-and-trade setting for their fictional economy.",
        (PORT_HISTORY,),
    ),
    LoreEntry(
        "tejo_wetlands",
        "Wetlands, birds and a reserve founded in 1976",
        "The Reserva Natural do Estuário do Tejo was established on 19 July 1976. "
        "Its landscapes include estuarine waters, saltmarshes, salt pans and "
        "agricultural floodplains. These habitats support birds including flamingos "
        "and avocets. The wider estuary provides feeding, nesting and resting areas "
        "for waterbirds, including birds stopping during migration. Its natural "
        "history sits alongside generations of fishing, salt production and other "
        "riverside livelihoods.",
        (RESERVE_HISTORY, ESTUARY_ECOLOGY),
    ),
    LoreEntry(
        "tejo_nursery",
        "An estuary that shelters young fish",
        "The Tejo estuary is a nursery where young fish and shrimp can grow. "
        "Regional conservation information identifies this role for species with "
        "commercial importance, including sole and sea bass. The estuary is also "
        "a transition area for migratory fish moving between marine and freshwater "
        "environments. Mudflats, saltmarshes, reed beds and connected waterways "
        "form part of this living system. The river's ecological value reaches "
        "beyond the ships and bridges visible from Lisbon's waterfront.",
        (ESTUARY_ECOLOGY,),
    ),
)

ALL_LORE = LANDMARK_LORE + TEJO_LORE

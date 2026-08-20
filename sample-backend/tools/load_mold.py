from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from moldes.loader import MOLDS_ROOT, load_mold
from .base import Tool


MoldPath = Literal[
    "informe-juridico.md",
    "proyecto-decreto.md",
    "resolucion_basica.md",
    "resolucion-adjudicacion.md",
    "resolucion-contratacion.md",
    "resolucion-convenio.md",
    "resolucion-exoneracion.md",
]


class LoadMoldInput(BaseModel):
    path: MoldPath = Field(description="Nombre exacto de uno de los moldes Markdown disponibles.")


class LoadMold(Tool[LoadMoldInput]):
    name = "load_mold"
    description = (
        "Carga uno de los moldes juridicos disponibles. Use exactamente uno de los valores permitidos en path; "
        "el molde define estructura y nunca constituye autoridad juridica."
    )
    input_schema = LoadMoldInput

    def execute(self, arguments: LoadMoldInput, context: dict[str, Any]) -> dict[str, object]:
        return load_mold(arguments.path, Path(context.get("molds_root", MOLDS_ROOT)))


tool = LoadMold()

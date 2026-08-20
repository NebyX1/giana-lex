import { useEffect, useState } from "react";
import {
  Badge,
  Button,
  Card,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Field,
  Input,
  MessageBar,
  MessageBarBody,
  Select,
  Spinner,
  Tab,
  TabList,
  Text,
  Textarea,
  Title1,
  Title3,
} from "@fluentui/react-components";
import {
  AddRegular,
  ArrowLeftRegular,
  ArrowSyncRegular,
  BookRegular,
  CheckmarkCircleRegular,
  DatabaseRegular,
  DocumentRegular,
  ErrorCircleRegular,
  OpenRegular,
  SearchRegular,
  TreeDeciduousRegular,
  WarningRegular,
} from "@fluentui/react-icons";
import { knowledgeApi } from "../../api.js";

const EMPTY_TAXONOMY = {
  parent_id: null,
  level: "family",
  code: "",
  slug: "",
  name: "",
  description: "",
  aliases: "",
  positive_signals: "",
  negative_signals: "",
  required_facts: "",
  recommended_facts: "",
  forbidden_assumptions: "",
  legal_notes: "",
  drafting_notes: "",
  status: "draft",
};

const listValue = (value) =>
  Array.isArray(value) ? value.join("\n") : value || "";
const listPayload = (value) =>
  value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);

function StatusBadge({ status }) {
  const labels = {
    synced: "Sincronizado",
    pending: "Pendiente",
    indexing: "Indexando",
    failed: "Error",
    stale: "Desactualizado",
    not_indexed: "Sin indexar",
    active: "Activo",
    draft: "Borrador",
    deprecated: "Deprecado",
    archived: "Archivado",
    validated: "Validado",
    import_review_required: "Requiere revisión",
  };
  const color = ["synced", "active", "validated"].includes(status)
    ? "success"
    : status === "failed"
      ? "danger"
      : ["pending", "stale", "import_review_required"].includes(status)
        ? "warning"
        : "informative";
  return (
    <Badge appearance="tint" color={color}>
      {labels[status] || status}
    </Badge>
  );
}

function Metric({ icon: Icon, label, value, help }) {
  return (
    <Card className="knowledge-metric">
      <div className="knowledge-metric-icon">
        <Icon />
      </div>
      <div>
        <Text className="muted" size={200} block>
          {label}
        </Text>
        <Text size={700} weight="semibold" block>
          {value ?? "—"}
        </Text>
        {help && (
          <Text className="muted" size={100}>
            {help}
          </Text>
        )}
      </div>
    </Card>
  );
}

export default function KnowledgeCenter({ onClose }) {
  const [tab, setTab] = useState("overview");
  const [overview, setOverview] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadBase = async () => {
    setError("");
    try {
      const [overviewResult, taxonomyResult] = await Promise.all([
        knowledgeApi.overview(),
        knowledgeApi.taxonomy(),
      ]);
      setOverview(overviewResult.overview);
      setNodes(taxonomyResult.nodes);
    } catch (caught) {
      setError(caught.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void loadBase();
  }, []);

  return (
    <main className="standalone-page knowledge-page">
      <header className="knowledge-header">
        <Button
          className="back-button"
          appearance="secondary"
          icon={<ArrowLeftRegular />}
          onClick={onClose}
        >
          Configuración
        </Button>
        <div className="knowledge-title-row">
          <div>
            <Text
              className="manager-eyebrow"
              size={100}
              weight="semibold"
              block
            >
              CONOCIMIENTO JURÍDICO
            </Text>
            <Title1>Tipologías y antecedentes</Title1>
            <Text className="muted">
              Fuente persistente para clasificación, retrieval y redacción
              administrativa.
            </Text>
          </div>
          {overview?.qdrant && (
            <div className="knowledge-health">
              <span data-ok={overview.qdrant.connected} />
              <div>
                <Text weight="semibold" block>
                  Qdrant
                </Text>
                <Text size={200} className="muted">
                  {overview.qdrant.connected ? "Conectado" : "Sin conexión"}
                </Text>
              </div>
            </div>
          )}
        </div>
      </header>
      <TabList
        className="knowledge-tabs"
        selectedValue={tab}
        onTabSelect={(_, data) => setTab(data.value)}
      >
        <Tab value="overview">Resumen</Tab>
        <Tab value="taxonomy">Tipologías</Tab>
        <Tab value="resolutions">Resoluciones</Tab>
        <Tab value="import">Importar</Tab>
        <Tab value="index">Estado del índice</Tab>
      </TabList>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      {loading ? (
        <Spinner label="Cargando conocimiento jurídico" />
      ) : (
        <>
          {tab === "overview" && (
            <Overview data={overview} onNavigate={setTab} />
          )}
          {tab === "taxonomy" && (
            <TaxonomyView nodes={nodes} onChanged={loadBase} />
          )}
          {tab === "resolutions" && <ResolutionsView nodes={nodes} />}
          {tab === "import" && (
            <ImportView nodes={nodes} onNodesChanged={loadBase} />
          )}
          {tab === "index" && <IndexView onOverviewChanged={loadBase} />}
        </>
      )}
    </main>
  );
}

function Overview({ data, onNavigate }) {
  if (!data) return null;
  return (
    <div className="knowledge-content">
      <div className="knowledge-metrics">
        <Metric
          icon={TreeDeciduousRegular}
          label="Tipologías activas"
          value={data.typologies_active}
        />
        <Metric
          icon={DocumentRegular}
          label="Resoluciones"
          value={data.resolutions}
        />
        <Metric
          icon={CheckmarkCircleRegular}
          label="Antecedentes canónicos"
          value={data.canonical_precedents}
        />
        <Metric
          icon={WarningRegular}
          label="Subtipos sin canónico"
          value={data.subtypes_without_canonical}
        />
        <Metric
          icon={ArrowSyncRegular}
          label="Pendientes de indexar"
          value={data.pending_index}
        />
        <Metric
          icon={ErrorCircleRegular}
          label="Errores de indexación"
          value={data.index_errors}
        />
      </div>
      <div className="knowledge-overview-grid">
        <Card className="knowledge-status-card">
          <Title3>Estado operativo</Title3>
          <div className="knowledge-status-line">
            <span data-ok={data.qdrant.connected} />
            <div>
              <Text weight="semibold" block>
                Qdrant
              </Text>
              <Text className="muted" size={200}>
                {data.qdrant.connected
                  ? `${data.qdrant.dimension} dimensiones · ${data.qdrant.embedding_model}`
                  : data.qdrant.error}
              </Text>
            </div>
          </div>
          <div className="knowledge-status-line">
            <span data-ok={data.qdrant.taxonomy_exists} />
            <div>
              <Text weight="semibold" block>
                Taxonomía
              </Text>
              <Text className="muted" size={200}>
                {data.qdrant.taxonomy_exists
                  ? "Colección disponible"
                  : "Pendiente de primera indexación"}
              </Text>
            </div>
          </div>
          <div className="knowledge-status-line">
            <span data-ok={data.qdrant.resolutions_exists} />
            <div>
              <Text weight="semibold" block>
                Resoluciones
              </Text>
              <Text className="muted" size={200}>
                {data.qdrant.resolutions_exists
                  ? "Colección disponible"
                  : "Pendiente de primera indexación"}
              </Text>
            </div>
          </div>
          <Button appearance="secondary" onClick={() => onNavigate("index")}>
            Ver estado detallado
          </Button>
        </Card>
        <Card className="knowledge-actions-card">
          <Title3>Acciones rápidas</Title3>
          <Button
            icon={<TreeDeciduousRegular />}
            onClick={() => onNavigate("taxonomy")}
          >
            Administrar tipologías
          </Button>
          <Button
            icon={<SearchRegular />}
            onClick={() => onNavigate("resolutions")}
          >
            Buscar resoluciones
          </Button>
          <Button
            appearance="primary"
            icon={<AddRegular />}
            onClick={() => onNavigate("import")}
          >
            Importar resolución oficial
          </Button>
        </Card>
      </div>
    </div>
  );
}

function TaxonomyView({ nodes, onChanged }) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(null);
  const [editor, setEditor] = useState(null);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const visible = nodes.filter(
    (node) =>
      !query ||
      `${node.code} ${node.name} ${node.description}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const selectNode = async (node) => {
    setSelected(node);
    setError("");
    try {
      setDetail((await knowledgeApi.taxonomyDetail(node.id)).node);
    } catch (caught) {
      setError(caught.message);
    }
  };
  const openCreate = (parent = null) =>
    setEditor({
      ...EMPTY_TAXONOMY,
      parent_id: parent?.id || null,
      level: parent
        ? parent.level === "family"
          ? "type"
          : "subtype"
        : "family",
      code: parent ? `${parent.code}.` : "",
    });
  const openEdit = (node) =>
    setEditor({
      ...node,
      aliases: listValue(node.aliases),
      positive_signals: listValue(node.positive_signals),
      negative_signals: listValue(node.negative_signals),
      required_facts: listValue(node.required_facts),
      recommended_facts: listValue(node.recommended_facts),
      forbidden_assumptions: listValue(node.forbidden_assumptions),
      expected_version: node.version,
    });
  const save = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    const payload = {
      ...editor,
      aliases: listPayload(editor.aliases),
      positive_signals: listPayload(editor.positive_signals),
      negative_signals: listPayload(editor.negative_signals),
      required_facts: listPayload(editor.required_facts),
      recommended_facts: listPayload(editor.recommended_facts),
      forbidden_assumptions: listPayload(editor.forbidden_assumptions),
    };
    try {
      if (editor.id) await knowledgeApi.updateTaxonomy(editor.id, payload);
      else await knowledgeApi.createTaxonomy(payload);
      setEditor(null);
      await onChanged();
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };
  const changeStatus = async (status) => {
    setBusy(true);
    try {
      await knowledgeApi.updateTaxonomy(selected.id, {
        status,
        expected_version: selected.version,
      });
      setSelected(null);
      setDetail(null);
      await onChanged();
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="knowledge-content">
      <div className="knowledge-toolbar">
        <Input
          contentBefore={<SearchRegular />}
          placeholder="Buscar por código, nombre o descripción…"
          value={query}
          onChange={(_, data) => setQuery(data.value)}
        />
        <Text className="muted" size={200}>
          {visible.length} nodos
        </Text>
        <Button
          appearance="primary"
          icon={<AddRegular />}
          onClick={() => openCreate()}
        >
          Nueva familia
        </Button>
      </div>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      <div className="taxonomy-layout">
        <Card className="taxonomy-tree" aria-label="Árbol de tipologías">
          {visible.map((node) => (
            <button
              key={node.id}
              className={`taxonomy-node level-${node.level} ${selected?.id === node.id ? "active" : ""}`}
              onClick={() => void selectNode(node)}
            >
              <span />
              <div>
                <strong>{node.name}</strong>
                <small>{node.code}</small>
              </div>
              <StatusBadge status={node.status} />
            </button>
          ))}
        </Card>
        <Card className="taxonomy-detail">
          {detail ? (
            <>
              <div className="taxonomy-detail-heading">
                <div>
                  <Text
                    className="manager-eyebrow"
                    size={100}
                    weight="semibold"
                    block
                  >
                    {detail.level.toUpperCase()}
                  </Text>
                  <Title3>{detail.name}</Title3>
                  <Text className="muted">{detail.code}</Text>
                </div>
                <StatusBadge status={detail.status} />
              </div>
              <p>{detail.description || "Sin descripción."}</p>
              <div className="knowledge-chip-list">
                {detail.aliases.map((alias) => (
                  <Badge key={alias} appearance="outline">
                    {alias}
                  </Badge>
                ))}
              </div>
              <DetailList
                title="Señales positivas"
                items={detail.positive_signals}
              />
              <DetailList
                title="Señales negativas"
                items={detail.negative_signals}
              />
              <DetailList
                title="Hechos obligatorios"
                items={detail.required_facts}
              />
              <DetailList
                title="Suposiciones prohibidas"
                items={detail.forbidden_assumptions}
              />
              <section className="taxonomy-relations">
                <h4>Antecedentes asociados</h4>
                {["canonical", "secondary", "related", "negative_example"].map(
                  (role) => (
                    <div key={role}>
                      <strong>{role.replace("_", " ")}</strong>
                      <span>
                        {
                          detail.assignments.filter(
                            (item) => item.role === role,
                          ).length
                        }
                      </span>
                    </div>
                  ),
                )}
              </section>
              <div className="knowledge-actions">
                <Button onClick={() => openEdit(detail)}>Editar</Button>
                {detail.level !== "subtype" && (
                  <Button
                    icon={<AddRegular />}
                    onClick={() => openCreate(detail)}
                  >
                    Nuevo hijo
                  </Button>
                )}
                <Button
                  onClick={() => void knowledgeApi.reindexTaxonomy(detail.id)}
                >
                  Reindexar
                </Button>
                {detail.status !== "active" && (
                  <Button onClick={() => void changeStatus("active")}>
                    Activar
                  </Button>
                )}
                {detail.status === "active" && (
                  <Button onClick={() => void changeStatus("deprecated")}>
                    Deprecar
                  </Button>
                )}
                <Button
                  appearance="subtle"
                  onClick={() => void changeStatus("archived")}
                >
                  Archivar
                </Button>
              </div>
            </>
          ) : (
            <div className="knowledge-empty">
              <TreeDeciduousRegular />
              <Text weight="semibold">Seleccione una tipología</Text>
              <Text className="muted">
                Consulte su configuración y antecedentes relacionados.
              </Text>
            </div>
          )}
        </Card>
      </div>
      <TaxonomyDialog
        value={editor}
        setValue={setEditor}
        nodes={nodes}
        busy={busy}
        error={error}
        onSave={save}
      />
    </div>
  );
}

function DetailList({ title, items }) {
  if (!items?.length) return null;
  return (
    <section className="knowledge-detail-list">
      <strong>{title}</strong>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function TaxonomyDialog({ value, setValue, nodes, busy, error, onSave }) {
  if (!value) return null;
  const update = (key, next) => setValue({ ...value, [key]: next });
  return (
    <Dialog
      open
      onOpenChange={(_, data) => {
        if (!data.open && !busy) setValue(null);
      }}
    >
      <DialogSurface className="taxonomy-dialog">
        <form onSubmit={onSave}>
          <DialogBody>
            <DialogTitle>
              {value.id ? "Editar tipología" : `Nueva ${value.level}`}
            </DialogTitle>
            <DialogContent className="knowledge-form">
              {error && (
                <MessageBar intent="error">
                  <MessageBarBody>{error}</MessageBarBody>
                </MessageBar>
              )}
              <div className="knowledge-form-grid">
                <Field label="Nivel">
                  <Select
                    value={value.level}
                    disabled={Boolean(value.id)}
                    onChange={(_, data) => update("level", data.value)}
                  >
                    <option value="family">Familia</option>
                    <option value="type">Tipo</option>
                    <option value="subtype">Subtipo</option>
                  </Select>
                </Field>
                <Field label="Padre">
                  <Select
                    value={value.parent_id || ""}
                    disabled={value.level === "family"}
                    onChange={(_, data) =>
                      update("parent_id", data.value || null)
                    }
                  >
                    <option value="">Sin padre</option>
                    {nodes
                      .filter((node) =>
                        value.level === "type"
                          ? node.level === "family"
                          : node.level === "type",
                      )
                      .map((node) => (
                        <option key={node.id} value={node.id}>
                          {node.code} · {node.name}
                        </option>
                      ))}
                  </Select>
                </Field>
                <Field label="Código" required>
                  <Input
                    value={value.code}
                    disabled={Boolean(value.id)}
                    onChange={(_, data) => update("code", data.value)}
                    required
                  />
                </Field>
                <Field label="Slug" required>
                  <Input
                    value={value.slug}
                    disabled={Boolean(value.id)}
                    onChange={(_, data) => update("slug", data.value)}
                    required
                  />
                </Field>
                <Field label="Nombre" required>
                  <Input
                    value={value.name}
                    onChange={(_, data) => update("name", data.value)}
                    required
                  />
                </Field>
                <Field label="Estado">
                  <Select
                    value={value.status}
                    onChange={(_, data) => update("status", data.value)}
                  >
                    <option value="draft">Borrador</option>
                    <option value="active">Activo</option>
                    <option value="deprecated">Deprecado</option>
                    <option value="archived">Archivado</option>
                  </Select>
                </Field>
              </div>
              <Field label="Descripción">
                <Textarea
                  value={value.description}
                  onChange={(_, data) => update("description", data.value)}
                />
              </Field>
              <div className="knowledge-form-grid">
                <Field label="Aliases" hint="Uno por línea">
                  <Textarea
                    value={value.aliases}
                    onChange={(_, data) => update("aliases", data.value)}
                  />
                </Field>
                <Field label="Señales positivas">
                  <Textarea
                    value={value.positive_signals}
                    onChange={(_, data) =>
                      update("positive_signals", data.value)
                    }
                  />
                </Field>
                <Field label="Señales negativas">
                  <Textarea
                    value={value.negative_signals}
                    onChange={(_, data) =>
                      update("negative_signals", data.value)
                    }
                  />
                </Field>
                <Field label="Hechos obligatorios">
                  <Textarea
                    value={value.required_facts}
                    onChange={(_, data) => update("required_facts", data.value)}
                  />
                </Field>
                <Field label="Hechos recomendados">
                  <Textarea
                    value={value.recommended_facts}
                    onChange={(_, data) =>
                      update("recommended_facts", data.value)
                    }
                  />
                </Field>
                <Field label="Suposiciones prohibidas">
                  <Textarea
                    value={value.forbidden_assumptions}
                    onChange={(_, data) =>
                      update("forbidden_assumptions", data.value)
                    }
                  />
                </Field>
              </div>
              <Field label="Notas jurídicas">
                <Textarea
                  value={value.legal_notes}
                  onChange={(_, data) => update("legal_notes", data.value)}
                />
              </Field>
              <Field label="Notas para redacción">
                <Textarea
                  value={value.drafting_notes}
                  onChange={(_, data) => update("drafting_notes", data.value)}
                />
              </Field>
            </DialogContent>
            <DialogActions>
              <Button
                type="button"
                disabled={busy}
                onClick={() => setValue(null)}
              >
                Cancelar
              </Button>
              <Button appearance="primary" type="submit" disabled={busy}>
                {busy ? <Spinner size="tiny" /> : "Guardar tipología"}
              </Button>
            </DialogActions>
          </DialogBody>
        </form>
      </DialogSurface>
    </Dialog>
  );
}

function ResolutionsView({ nodes }) {
  const [filters, setFilters] = useState({
    q: "",
    year: "",
    status: "",
    role: "",
    taxonomy_node_id: "",
    index_status: "",
    order: "recent",
    page: 1,
    page_size: 25,
  });
  const [data, setData] = useState({
    items: [],
    total: 0,
    page: 1,
    page_size: 25,
  });
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setData(await knowledgeApi.resolutions(filters));
    } catch (caught) {
      setError(caught.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    const timer = setTimeout(() => void load(), filters.q ? 250 : 0);
    return () => clearTimeout(timer);
  }, [JSON.stringify(filters)]);
  const open = async (id) => {
    setError("");
    try {
      setSelected((await knowledgeApi.resolution(id)).resolution);
    } catch (caught) {
      setError(caught.message);
    }
  };
  const updateFilter = (key, value) =>
    setFilters({ ...filters, [key]: value, page: key === "page" ? value : 1 });
  return (
    <div className="knowledge-content">
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      <div className="resolution-filters">
        <Input
          contentBefore={<SearchRegular />}
          placeholder="Buscar por número, título o contenido…"
          value={filters.q}
          onChange={(_, data) => updateFilter("q", data.value)}
        />
        <Select
          value={filters.taxonomy_node_id}
          onChange={(_, data) => updateFilter("taxonomy_node_id", data.value)}
        >
          <option value="">Todas las tipologías</option>
          {nodes
            .filter((node) => node.level === "subtype")
            .map((node) => (
              <option value={node.id} key={node.id}>
                {node.code}
              </option>
            ))}
        </Select>
        <Input
          type="number"
          placeholder="Año"
          value={filters.year}
          onChange={(_, data) => updateFilter("year", data.value)}
        />
        <Select
          value={filters.status}
          onChange={(_, data) => updateFilter("status", data.value)}
        >
          <option value="">Todos los estados</option>
          <option value="active">Activas</option>
          <option value="draft">Borradores</option>
          <option value="archived">Archivadas</option>
        </Select>
        <Select
          value={filters.role}
          onChange={(_, data) => updateFilter("role", data.value)}
        >
          <option value="">Todos los roles</option>
          <option value="canonical">Canónico</option>
          <option value="secondary">Secundario</option>
          <option value="related">Relacionado</option>
          <option value="negative_example">Ejemplo negativo</option>
        </Select>
        <Select
          value={filters.index_status}
          onChange={(_, data) => updateFilter("index_status", data.value)}
        >
          <option value="">Cualquier indexación</option>
          <option value="synced">Sincronizadas</option>
          <option value="pending">Pendientes</option>
          <option value="failed">Con error</option>
          <option value="stale">Desactualizadas</option>
        </Select>
        <Select
          value={filters.order}
          onChange={(_, data) => updateFilter("order", data.value)}
        >
          <option value="recent">Más recientes</option>
          <option value="oldest">Más antiguas</option>
          <option value="number">Número</option>
        </Select>
      </div>
      <div className="knowledge-table-wrap">
        <table className="knowledge-table">
          <thead>
            <tr>
              <th>Resolución</th>
              <th>Título</th>
              <th>Año</th>
              <th>Tipologías</th>
              <th>Estado</th>
              <th>Indexación</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7}>
                  <Spinner label="Buscando resoluciones" />
                </td>
              </tr>
            ) : (
              data.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <strong>{item.resolution_number}</strong>
                  </td>
                  <td>
                    <strong>{item.title}</strong>
                    <small>{item.official_summary}</small>
                  </td>
                  <td>{item.year || "—"}</td>
                  <td>{item.assignments.length}</td>
                  <td>
                    <StatusBadge status={item.status} />
                  </td>
                  <td>
                    <StatusBadge status={item.index_status} />
                  </td>
                  <td>
                    <Button
                      appearance="subtle"
                      onClick={() => void open(item.id)}
                    >
                      Abrir
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="knowledge-pagination">
        <Text className="muted">
          {data.total} resultados · página {data.page}
        </Text>
        <div>
          <Button
            disabled={data.page <= 1}
            onClick={() => updateFilter("page", data.page - 1)}
          >
            Anterior
          </Button>
          <Button
            disabled={data.page * data.page_size >= data.total}
            onClick={() => updateFilter("page", data.page + 1)}
          >
            Siguiente
          </Button>
        </div>
      </div>
      {selected && (
        <ResolutionDetail
          value={selected}
          nodes={nodes}
          onClose={() => setSelected(null)}
          onSaved={async () => {
            await load();
            const refreshed = await knowledgeApi.resolution(selected.id);
            setSelected(refreshed.resolution);
          }}
        />
      )}
    </div>
  );
}

function ResolutionDetail({ value, nodes, onClose, onSaved }) {
  const [tab, setTab] = useState("text");
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value.revisions[0]?.normalized_text || "");
  const [assignments, setAssignments] = useState(value.assignments);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const current = value.revisions[0] || {};
  const save = async () => {
    setBusy(true);
    setError("");
    try {
      await knowledgeApi.updateResolution(value.id, {
        normalized_text: text,
        change_reason: "Edición desde Configuración",
        assignments: assignments.map(
          ({ taxonomy_node_id, role, priority, notes }) => ({
            taxonomy_node_id,
            role,
            priority,
            notes,
          }),
        ),
        expected_version: value.version,
      });
      setEditing(false);
      await onSaved();
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };
  const addAssignment = () =>
    setAssignments([
      ...assignments,
      {
        taxonomy_node_id:
          nodes.find((node) => node.level === "subtype")?.id || "",
        role: "related",
        priority: 100,
        notes: "",
      },
    ]);
  return (
    <div className="resolution-drawer">
      <div className="resolution-drawer-header">
        <div>
          <Text className="manager-eyebrow" size={100} weight="semibold" block>
            RESOLUCIÓN N° {value.resolution_number}
          </Text>
          <Title3>{value.title}</Title3>
          <Text className="muted">
            {value.resolution_date ||
              value.publication_date ||
              "Fecha no indicada"}
          </Text>
        </div>
        <Button onClick={onClose}>Cerrar</Button>
      </div>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      <div className="resolution-source-row">
        <StatusBadge status={value.status} />
        <StatusBadge status={value.review_status} />
        <Button
          as="a"
          href={value.source_url}
          target="_blank"
          rel="noopener noreferrer"
          appearance="subtle"
          icon={<OpenRegular />}
        >
          Fuente oficial
        </Button>
      </div>
      <TabList
        selectedValue={tab}
        onTabSelect={(_, data) => setTab(data.value)}
      >
        <Tab value="text">Texto</Tab>
        <Tab value="structure">Estructura</Tab>
        <Tab value="taxonomy">Tipologías</Tab>
        <Tab value="history">Historial</Tab>
        <Tab value="index">Indexación</Tab>
      </TabList>
      <div className="resolution-drawer-body">
        {tab === "text" && (
          <>
            {editing ? (
              <Textarea
                className="resolution-editor"
                value={text}
                onChange={(_, data) => setText(data.value)}
              />
            ) : (
              <pre className="resolution-text">{current.normalized_text}</pre>
            )}
            <div className="knowledge-actions">
              {editing ? (
                <>
                  <Button onClick={() => setEditing(false)}>Cancelar</Button>
                  <Button
                    appearance="primary"
                    disabled={busy}
                    onClick={() => void save()}
                  >
                    Guardar nueva revisión
                  </Button>
                </>
              ) : (
                <Button onClick={() => setEditing(true)}>
                  Editar normalización
                </Button>
              )}
            </div>
          </>
        )}
        {tab === "structure" && (
          <div className="resolution-sections">
            {[
              ["VISTO", current.visto],
              ["RESULTANDO", current.resultandos],
              ["CONSIDERANDO", current.considerandos],
              ["ATENTO", current.atento],
              ["RESUELVE", current.resuelve],
            ].map(([name, content]) =>
              content?.length ? (
                <section key={name}>
                  <span>{name}</span>
                  {Array.isArray(content) ? (
                    content.map((item, index) => <p key={index}>{item}</p>)
                  ) : (
                    <p>{content}</p>
                  )}
                </section>
              ) : null,
            )}
          </div>
        )}
        {tab === "taxonomy" && (
          <>
            <div className="assignment-list">
              {assignments.map((item, index) => (
                <div key={`${item.taxonomy_node_id}-${index}`}>
                  <Select
                    value={item.taxonomy_node_id}
                    onChange={(_, data) =>
                      setAssignments(
                        assignments.map((entry, position) =>
                          position === index
                            ? { ...entry, taxonomy_node_id: data.value }
                            : entry,
                        ),
                      )
                    }
                  >
                    {nodes
                      .filter((node) => node.level === "subtype")
                      .map((node) => (
                        <option value={node.id} key={node.id}>
                          {node.code}
                        </option>
                      ))}
                  </Select>
                  <Select
                    value={item.role}
                    onChange={(_, data) =>
                      setAssignments(
                        assignments.map((entry, position) =>
                          position === index
                            ? { ...entry, role: data.value }
                            : entry,
                        ),
                      )
                    }
                  >
                    <option value="canonical">Canónica</option>
                    <option value="secondary">Secundaria</option>
                    <option value="related">Relacionada</option>
                    <option value="negative_example">Ejemplo negativo</option>
                  </Select>
                  <Button
                    appearance="subtle"
                    onClick={() =>
                      setAssignments(
                        assignments.filter((_, position) => position !== index),
                      )
                    }
                  >
                    Quitar
                  </Button>
                </div>
              ))}
            </div>
            <div className="knowledge-actions">
              <Button icon={<AddRegular />} onClick={addAssignment}>
                Agregar relación
              </Button>
              <Button
                appearance="primary"
                disabled={busy}
                onClick={() => void save()}
              >
                Guardar relaciones
              </Button>
            </div>
          </>
        )}
        {tab === "history" && (
          <div className="revision-history">
            {value.revisions.map((revision) => (
              <Card key={revision.id}>
                <Text weight="semibold" block>
                  Revisión {revision.revision_number}
                </Text>
                <Text className="muted" size={200}>
                  {revision.source} · {revision.created_at}
                </Text>
                <p>{revision.change_reason}</p>
              </Card>
            ))}
          </div>
        )}
        {tab === "index" && (
          <Card className="index-detail">
            <dl>
              <dt>Versión documento</dt>
              <dd>{value.version}</dd>
              <dt>Versión indexada</dt>
              <dd>{value.indexed_version || "—"}</dd>
              <dt>Estado</dt>
              <dd>
                <StatusBadge status={value.index_status} />
              </dd>
              <dt>Modelo</dt>
              <dd>Configurado en el servicio de indexación</dd>
            </dl>
            <Button
              icon={<ArrowSyncRegular />}
              onClick={() => void knowledgeApi.reindexResolution(value.id)}
            >
              Reindexar sin duplicar chunks
            </Button>
          </Card>
        )}
      </div>
    </div>
  );
}

function ImportView({ nodes, onNodesChanged }) {
  const [mode, setMode] = useState("url");
  const [url, setUrl] = useState("");
  const [preview, setPreview] = useState(null);
  const [taxonomyId, setTaxonomyId] = useState("");
  const [role, setRole] = useState("canonical");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [quickType, setQuickType] = useState(null);
  const analyze = async () => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await knowledgeApi.importUrl({ url, confirm: false });
      setPreview(response.preview);
      setTaxonomyId(response.preview.suggestions[0]?.taxonomy_node_id || "");
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };
  const confirm = async () => {
    setBusy(true);
    setError("");
    try {
      const assignments = taxonomyId
        ? [{ taxonomy_node_id: taxonomyId, role, priority: 100 }]
        : [];
      const response = await knowledgeApi.importUrl({
        url,
        confirm: true,
        assignments,
      });
      setNotice(
        response.duplicate
          ? "La resolución ya existía; no se duplicó."
          : "Resolución guardada. La indexación continuará en segundo plano.",
      );
      setPreview(null);
      setUrl("");
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="knowledge-content import-layout">
      <Card className="import-card">
        <TabList
          selectedValue={mode}
          onTabSelect={(_, data) => setMode(data.value)}
        >
          <Tab value="url">URL oficial</Tab>
          <Tab value="manual">Carga manual</Tab>
          <Tab value="file">Archivo</Tab>
        </TabList>
        {error && (
          <MessageBar intent="error">
            <MessageBarBody>{error}</MessageBarBody>
          </MessageBar>
        )}
        {notice && (
          <MessageBar intent="success">
            <MessageBarBody>{notice}</MessageBarBody>
          </MessageBar>
        )}
        {mode === "url" && (
          <div className="import-step">
            <div>
              <Text
                className="manager-eyebrow"
                size={100}
                weight="semibold"
                block
              >
                PASO 1
              </Text>
              <Title3>Analizar fuente oficial</Title3>
              <Text className="muted">
                Solo se admiten fichas de normativa de la Intendencia de
                Lavalleja en gub.uy.
              </Text>
            </div>
            <Field label="URL oficial" required>
              <Input
                value={url}
                onChange={(_, data) => setUrl(data.value)}
                placeholder="https://www.gub.uy/intendencia-lavalleja/institucional/normativa/resolucion-n-…"
              />
            </Field>
            <Button
              appearance="primary"
              disabled={!url.trim() || busy}
              onClick={() => void analyze()}
            >
              {busy ? <Spinner size="tiny" /> : "Analizar y previsualizar"}
            </Button>
          </div>
        )}
        {mode === "manual" && <ManualResolutionForm nodes={nodes} />}
        {mode === "file" && <FileResolutionForm nodes={nodes} />}
      </Card>
      {preview && (
        <Card className="import-preview">
          <Text className="manager-eyebrow" size={100} weight="semibold" block>
            PREVISUALIZACIÓN
          </Text>
          <Title3>{preview.parsed.title}</Title3>
          <div className="import-preview-meta">
            <strong>N° {preview.parsed.resolution_number}</strong>
            <span>
              {preview.parsed.resolution_date ||
                preview.parsed.publication_date}
            </span>
            <StatusBadge status={preview.validation.status} />
          </div>
          <Text>{preview.parsed.official_summary}</Text>
          <div className="resolution-sections">
            {[
              ["VISTO", preview.parsed.visto],
              ["CONSIDERANDO", preview.parsed.considerandos],
              ["ATENTO", preview.parsed.atento],
              ["RESUELVE", preview.parsed.resuelve],
            ].map(([name, content]) =>
              content?.length ? (
                <section key={name}>
                  <span>{name}</span>
                  <p>{Array.isArray(content) ? content.join("\n") : content}</p>
                </section>
              ) : null,
            )}
          </div>
          <Field label="Tipología confirmada">
            <Select
              value={taxonomyId}
              onChange={(_, data) => setTaxonomyId(data.value)}
            >
              <option value="">Sin asignar</option>
              {nodes
                .filter((node) => node.level === "subtype")
                .map((node) => (
                  <option key={node.id} value={node.id}>
                    {node.code} · {node.name}
                  </option>
                ))}
            </Select>
          </Field>
          <Field label="Rol">
            <Select value={role} onChange={(_, data) => setRole(data.value)}>
              <option value="canonical">Canónica</option>
              <option value="secondary">Secundaria</option>
              <option value="related">Relacionada</option>
              <option value="negative_example">Ejemplo negativo</option>
            </Select>
          </Field>
          <div className="classification-suggestions">
            <strong>Sugerencias por similitud</strong>
            {preview.suggestions.map((item) => (
              <button
                key={item.taxonomy_node_id}
                onClick={() => setTaxonomyId(item.taxonomy_node_id)}
              >
                <span>{item.subtype}</span>
                <small>Similitud {item.score.toFixed(3)}</small>
              </button>
            ))}
          </div>
          <Button
            appearance="subtle"
            icon={<AddRegular />}
            onClick={() =>
              setQuickType({ parent_id: "", code: "", slug: "", name: "" })
            }
          >
            Crear nueva tipología
          </Button>
          <Button
            appearance="primary"
            disabled={busy || preview.validation.status !== "validated"}
            onClick={() => void confirm()}
          >
            {busy ? <Spinner size="tiny" /> : "Confirmar y guardar"}
          </Button>
        </Card>
      )}
      <QuickTaxonomyDialog
        value={quickType}
        setValue={setQuickType}
        nodes={nodes}
        onCreated={async (node) => {
          await onNodesChanged();
          setTaxonomyId(node.id);
          setQuickType(null);
        }}
      />
    </div>
  );
}

function ManualResolutionForm({ nodes }) {
  const [form, setForm] = useState({
    resolution_number: "",
    title: "",
    official_summary: "",
    normalized_text: "",
    status: "draft",
    taxonomy_node_id: "",
  });
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    setError("");
    try {
      await knowledgeApi.createResolution({
        ...form,
        assignments: form.taxonomy_node_id
          ? [
              {
                taxonomy_node_id: form.taxonomy_node_id,
                role: "related",
                priority: 100,
              },
            ]
          : [],
      });
      setNotice("Resolución creada como borrador.");
    } catch (caught) {
      setError(caught.message);
    }
  };
  return (
    <form className="knowledge-form import-step" onSubmit={submit}>
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      {notice && (
        <MessageBar intent="success">
          <MessageBarBody>{notice}</MessageBarBody>
        </MessageBar>
      )}
      <Field label="Número" required>
        <Input
          value={form.resolution_number}
          onChange={(_, data) =>
            setForm({ ...form, resolution_number: data.value })
          }
          required
        />
      </Field>
      <Field label="Título" required>
        <Input
          value={form.title}
          onChange={(_, data) => setForm({ ...form, title: data.value })}
          required
        />
      </Field>
      <Field label="Resumen">
        <Input
          value={form.official_summary}
          onChange={(_, data) =>
            setForm({ ...form, official_summary: data.value })
          }
        />
      </Field>
      <Field label="Tipología inicial">
        <Select
          value={form.taxonomy_node_id}
          onChange={(_, data) =>
            setForm({ ...form, taxonomy_node_id: data.value })
          }
        >
          <option value="">Sin asignar</option>
          {nodes
            .filter((node) => node.level === "subtype")
            .map((node) => (
              <option value={node.id} key={node.id}>
                {node.code}
              </option>
            ))}
        </Select>
      </Field>
      <Field label="Texto normalizado" required>
        <Textarea
          value={form.normalized_text}
          onChange={(_, data) =>
            setForm({ ...form, normalized_text: data.value })
          }
          required
        />
      </Field>
      <Button appearance="primary" type="submit">
        Guardar borrador manual
      </Button>
    </form>
  );
}

function FileResolutionForm({ nodes }) {
  const [file, setFile] = useState(null);
  const [form, setForm] = useState({
    resolution_number: "",
    title: "",
    official_summary: "",
    status: "draft",
    taxonomy_node_id: "",
  });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await knowledgeApi.importFile(file, {
        ...form,
        assignments: form.taxonomy_node_id
          ? [{ taxonomy_node_id: form.taxonomy_node_id, role: "related", priority: 100 }]
          : [],
      });
      setNotice("Archivo preservado y resolución creada como borrador.");
      setFile(null);
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="knowledge-form import-step" onSubmit={submit}>
      {error && <MessageBar intent="error"><MessageBarBody>{error}</MessageBarBody></MessageBar>}
      {notice && <MessageBar intent="success"><MessageBarBody>{notice}</MessageBarBody></MessageBar>}
      <Field label="Archivo" hint="PDF, DOCX, TXT o MD. Máximo 10 MB." required>
        <input type="file" accept=".pdf,.docx,.txt,.md" onChange={(event) => setFile(event.target.files?.[0] || null)} required />
      </Field>
      <Field label="Número" required><Input value={form.resolution_number} onChange={(_, data) => setForm({ ...form, resolution_number: data.value })} required /></Field>
      <Field label="Título" required><Input value={form.title} onChange={(_, data) => setForm({ ...form, title: data.value })} required /></Field>
      <Field label="Tipología inicial"><Select value={form.taxonomy_node_id} onChange={(_, data) => setForm({ ...form, taxonomy_node_id: data.value })}><option value="">Sin asignar</option>{nodes.filter((node) => node.level === "subtype").map((node) => <option value={node.id} key={node.id}>{node.code}</option>)}</Select></Field>
      <Button appearance="primary" type="submit" disabled={!file || busy}>{busy ? <Spinner size="tiny" /> : "Preservar y extraer"}</Button>
    </form>
  );
}

function QuickTaxonomyDialog({ value, setValue, nodes, onCreated }) {
  if (!value) return null;
  const submit = async (event) => {
    event.preventDefault();
    const response = await knowledgeApi.createTaxonomy({
      ...value,
      level: "subtype",
      description: value.name,
      status: "active",
    });
    await onCreated(response.node);
  };
  return (
    <Dialog
      open
      onOpenChange={(_, data) => {
        if (!data.open) setValue(null);
      }}
    >
      <DialogSurface>
        <form onSubmit={submit}>
          <DialogBody>
            <DialogTitle>Nueva tipología durante la importación</DialogTitle>
            <DialogContent className="knowledge-form">
              <Field label="Tipo padre" required>
                <Select
                  value={value.parent_id}
                  onChange={(_, data) =>
                    setValue({ ...value, parent_id: data.value })
                  }
                  required
                >
                  <option value="">Seleccione</option>
                  {nodes
                    .filter((node) => node.level === "type")
                    .map((node) => (
                      <option value={node.id} key={node.id}>
                        {node.code} · {node.name}
                      </option>
                    ))}
                </Select>
              </Field>
              <Field label="Código completo" required>
                <Input
                  value={value.code}
                  onChange={(_, data) =>
                    setValue({ ...value, code: data.value })
                  }
                  required
                />
              </Field>
              <Field label="Slug" required>
                <Input
                  value={value.slug}
                  onChange={(_, data) =>
                    setValue({ ...value, slug: data.value })
                  }
                  required
                />
              </Field>
              <Field label="Nombre" required>
                <Input
                  value={value.name}
                  onChange={(_, data) =>
                    setValue({ ...value, name: data.value })
                  }
                  required
                />
              </Field>
            </DialogContent>
            <DialogActions>
              <Button type="button" onClick={() => setValue(null)}>
                Cancelar
              </Button>
              <Button appearance="primary" type="submit">
                Crear y seleccionar
              </Button>
            </DialogActions>
          </DialogBody>
        </form>
      </DialogSurface>
    </Dialog>
  );
}

function IndexView({ onOverviewChanged }) {
  const [data, setData] = useState(null);
  const [check, setCheck] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const load = async () => {
    try {
      setData(await knowledgeApi.indexStatus());
    } catch (caught) {
      setError(caught.message);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  const action = async (fn) => {
    setBusy(true);
    setError("");
    try {
      const result = await fn();
      if (result.issues) setCheck(result);
      await load();
      await onOverviewChanged();
    } catch (caught) {
      setError(caught.message);
    } finally {
      setBusy(false);
    }
  };
  if (!data) return <Spinner />;
  return (
    <div className="knowledge-content">
      {error && (
        <MessageBar intent="error">
          <MessageBarBody>{error}</MessageBarBody>
        </MessageBar>
      )}
      <div className="index-grid">
        <Card className="index-card">
          <div className="index-card-heading">
            <DatabaseRegular />
            <div>
              <Title3>Qdrant</Title3>
              <Text className="muted">
                {data.qdrant.connected ? "Servicio conectado" : "No disponible"}
              </Text>
            </div>
            <StatusBadge status={data.qdrant.connected ? "synced" : "failed"} />
          </div>
          <dl>
            <dt>Modelo</dt>
            <dd>{data.qdrant.embedding_model}</dd>
            <dt>Dimensiones</dt>
            <dd>{data.qdrant.dimension}</dd>
            <dt>Taxonomía</dt>
            <dd>{data.qdrant.taxonomy_collection}</dd>
            <dt>Resoluciones</dt>
            <dd>{data.qdrant.resolutions_collection}</dd>
          </dl>
        </Card>
        <Card className="index-card">
          <div className="index-card-heading">
            <ArrowSyncRegular />
            <div>
              <Title3>Cola de sincronización</Title3>
              <Text className="muted">Outbox persistente</Text>
            </div>
          </div>
          <dl>
            {Object.entries(data.outbox).map(([status, count]) => (
              <div key={status}>
                <dt>{status}</dt>
                <dd>{count}</dd>
              </div>
            ))}
          </dl>
          <Button
            disabled={busy}
            onClick={() => void action(knowledgeApi.retryFailed)}
          >
            Reintentar fallidos
          </Button>
        </Card>
      </div>
      <div className="knowledge-actions">
        <Button
          appearance="primary"
          disabled={busy}
          onClick={() => void action(knowledgeApi.checkIndex)}
        >
          Comprobar consistencia
        </Button>
        <Button
          icon={<ArrowSyncRegular />}
          disabled={busy}
          onClick={() => void action(knowledgeApi.retryFailed)}
        >
          Procesar errores
        </Button>
      </div>
      {data.failed_events.length > 0 && (
        <div className="knowledge-table-wrap">
          <table className="knowledge-table">
            <thead>
              <tr>
                <th>Entidad</th>
                <th>Versión</th>
                <th>Intentos</th>
                <th>Error</th>
              </tr>
            </thead>
            <tbody>
              {data.failed_events.map((event) => (
                <tr key={event.id}>
                  <td>
                    {event.entity_type} · {event.entity_id}
                  </td>
                  <td>{event.entity_version}</td>
                  <td>{event.attempts}</td>
                  <td>{event.last_error}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {check && (
        <Card className="consistency-results">
          <Title3>Resultado de consistencia</Title3>
          <Text>
            {check.issue_count} incidencias detectadas. No se aplicaron
            reparaciones destructivas.
          </Text>
          {check.issues.slice(0, 100).map((issue, index) => (
            <div key={index}>
              <StatusBadge status="pending" />
              <code>{issue.kind}</code>
              <span>{issue.code || issue.entity_id}</span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

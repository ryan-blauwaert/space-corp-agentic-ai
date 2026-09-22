import type { QuestionResponse } from "./api/questions";

const labels: Record<string, string> = {
  facility_equipment: "Facility equipment",
  compatible_stock: "Compatible stock",
  work_orders: "Work orders",
  incidents: "Incidents",
  inventory: "Inventory",
  operation: "Records to retrieve",
  facility: "Facility filters",
  facility_id: "Facility ID",
  facility_type: "Facility type",
  equipment_model_id: "Equipment model ID",
  compatible_model_id: "Compatible equipment model ID",
  equipment_unit_id: "Equipment unit ID",
  unit_statuses: "Equipment statuses",
  incident_statuses: "Incident statuses",
  target_equipment_unit_id: "Direct work target unit ID",
  originating_incident_id: "Originating incident ID",
  incident_equipment_unit_id: "Incident-affected unit ID",
  as_of: "As of (UTC)",
  occurred: "Occurrence window",
  start: "Start (inclusive)",
  end: "End (exclusive)",
  quantity: "Quantity on hand filter",
  below_reorder_point: "Below reorder point",
  operator: "Comparison",
  value: "Quantity threshold",
  fault_code: "Fault code",
  lt: "Less than",
  lte: "Less than or equal to",
  eq: "Equal to",
  gte: "Greater than or equal to",
  gt: "Greater than",
};
export const fieldLabel = (key: string) =>
  labels[key] ?? key.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());

// Literal values are text nodes, never HTML or Markdown. No facts are inferred here.
export function RecordFields({
  value,
  scope = false,
}: {
  value: unknown;
  scope?: boolean;
}) {
  if (value === null || value === undefined)
    return (
      <span className="muted">
        {scope ? "No restriction" : "Not recorded / unknown"}
      </span>
    );
  if (Array.isArray(value)) {
    if (!value.length) return <span className="muted">None returned</span>;
    if (value.every((item) => typeof item === "string"))
      return (
        <span>
          {scope ? "Any of: " : ""}
          {value.join(", ")}
        </span>
      );
    return (
      <ol className="nested-records">
        {value.map((item, index) => (
          <li key={index}>
            <RecordFields value={item} scope={scope} />
          </li>
        ))}
      </ol>
    );
  }
  if (typeof value === "object")
    return (
      <dl className="record-fields">
        {Object.entries(value).map(([key, item]) => (
          <div key={key}>
            <dt>{fieldLabel(key)}</dt>
            <dd>
              {(key === "operation" || key === "operator") &&
              typeof item === "string" ? (
                fieldLabel(item)
              ) : (
                <RecordFields value={item} scope={scope} />
              )}
            </dd>
          </div>
        ))}
      </dl>
    );
  return (
    <span>
      {typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}
    </span>
  );
}

export function QueryScope({ data }: { data: QuestionResponse }) {
  return (
    <>
      <p className="scope-note">
        All filters below apply together. “No restriction” means that field does
        not narrow the search. Listed alternatives mean any of those values.
      </p>
      <RecordFields value={data.plan} scope />
      <p className="scope-page">
        Result page: up to <strong>{data.page.limit}</strong> records, starting
        at record <strong>{data.page.offset + 1}</strong>.
      </p>
    </>
  );
}

const cautiousTitles: Record<string, string> = {
  no_results: "No matching records",
  insufficient_evidence: "Not enough evidence",
  declined: "Question needs attention",
  invalid_answer: "Answer withheld",
  model_failure: "Question service unavailable",
  awaiting_confirmation: "Review required",
};
export function AnswerDetails({ data }: { data: QuestionResponse }) {
  const { outcome, evidence } = data;
  return (
    <>
      <div className="answer-heading">
        <h2>
          {outcome.status === "answered"
            ? "Mission briefing"
            : cautiousTitles[outcome.reason]}
        </h2>
        {outcome.status === "answered" && (
          <span className={`coverage ${outcome.coverage}`}>
            {outcome.coverage === "partial"
              ? "Partial results"
              : "Complete result"}
          </span>
        )}
      </div>
      <p className="answer-text">
        {outcome.status === "answered" ? outcome.answer.text : outcome.text}
      </p>
      {data.plan.operation === "declined" && (
        <p className="scope-note">
          Reason: {fieldLabel(data.plan.reason)}. No query results were
          retrieved.
        </p>
      )}
      {data.plan.operation !== "declined" && (
        <details className="answer-disclosure">
          <summary>Query scope</summary>
          <QueryScope data={data} />
        </details>
      )}
      {evidence && (
        <details className="answer-disclosure">
          <summary>
            Supporting records · {evidence.page.rows.length} returned of{" "}
            {evidence.page.total}
          </summary>
          <p className="scope-note">
            These are the records returned for this answer. Other pages are not
            fetched automatically.
          </p>
          {"incident_ids" in evidence && (
            <div>
              <h3>Supporting incident IDs</h3>
              <RecordFields value={evidence.incident_ids} />
            </div>
          )}
          {"status" in evidence && (
            <p>Stock lookup: {fieldLabel(evidence.status)}</p>
          )}
          {evidence.page.rows.length ? (
            <ol className="evidence-records">
              {evidence.page.rows.map((row, index) => (
                <li key={index}>
                  <h3>Record {evidence.page.offset + index + 1}</h3>
                  <RecordFields value={row} />
                </li>
              ))}
            </ol>
          ) : (
            <p>No records were returned on this page.</p>
          )}
        </details>
      )}
      {outcome.status === "answered" && (
        <details className="answer-disclosure">
          <summary>
            Record references · {outcome.answer.references.length}
          </summary>
          <ul className="reference-list">
            {outcome.answer.references.map((ref) => (
              <li key={`${ref.entity}:${ref.record_id}`}>
                <strong>{fieldLabel(ref.entity)}</strong>
                <span>{ref.record_id}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

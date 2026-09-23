import { Brand } from "./Brand";
import { QuestionScreen } from "./QuestionScreen";
import { useCallback, useEffect, useRef } from "react";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { get } from "./api/client";
import { useResource } from "./useResource";
import type { components } from "./api/generated";

type Pagination = components["schemas"]["PaginationMetadata"];
const PAGE_SIZE = 10;
const label = (value: string) => value.replaceAll("_", " ");

function Status({ value }: { value: string }) {
  return (
    <span className={`status ${value}`}>
      <span aria-hidden="true">●</span> {label(value)}
    </span>
  );
}
function Notice({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="notice" role={retry ? "alert" : "status"}>
      <p>{message}</p>
      {retry && <button onClick={retry}>Try again</button>}
    </div>
  );
}
function Pager({ page }: { page: Pagination }) {
  const [, setParams] = useSearchParams();
  const last = page.offset + page.limit >= page.total;
  return (
    <nav className="pager" aria-label="Results pages">
      <span>
        {page.total === 0
          ? "0 records"
          : page.offset >= page.total
            ? `0 on this page · ${page.total} total`
            : `${Math.min(page.offset + 1, page.total)}–${Math.min(page.offset + page.limit, page.total)} of ${page.total}`}
      </span>
      <div>
        <button
          disabled={page.offset === 0}
          onClick={() =>
            setParams({ offset: String(Math.max(0, page.offset - page.limit)) })
          }
        >
          Previous
        </button>
        <button
          disabled={last}
          onClick={() =>
            setParams({ offset: String(page.offset + page.limit) })
          }
        >
          Next
        </button>
      </div>
    </nav>
  );
}
function useOffset() {
  const [params] = useSearchParams();
  const raw = params.get("offset") ?? "0";
  const value = Number(raw);
  return /^\d+$/.test(raw) && Number.isSafeInteger(value) && value >= 0
    ? value
    : null;
}
function Facilities({ offset }: { offset: number }) {
  const load = useCallback(
    (signal: AbortSignal) =>
      get(
        "/facilities",
        `/facilities?limit=${PAGE_SIZE}&offset=${offset}`,
        signal,
      ),
    [offset],
  );
  const { state, retry } = useResource(load);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">OPERATIONS / FACILITIES</p>
          <h1>Mission control</h1>
          <p className="lede">
            From Earth to the lunar frontier, check in on our facilities and the
            equipment keeping them running.
          </p>
        </div>
        <span className="read-only">Read only</span>
      </div>
      <section className="panel" aria-labelledby="facilities-heading">
        <div className="panel-heading">
          <h2 id="facilities-heading">Facility network</h2>
          <span>Current workspace</span>
        </div>
        {state.status === "loading" && <Notice message="Loading facilities…" />}
        {state.status === "error" && (
          <Notice message={state.message} retry={retry} />
        )}
        {state.status === "ready" && (
          <>
            {state.data.items.length === 0 ? (
              <Notice
                message={
                  state.data.pagination.total
                    ? "No facilities on this page. Use Previous to return."
                    : "No facilities are available in this workspace."
                }
              />
            ) : (
              <div className="facility-grid">
                {state.data.items.map((facility) => (
                  <Link
                    className="facility-card"
                    key={facility.id}
                    to={`/facilities/${facility.id}`}
                  >
                    <div className="card-top">
                      <span className="code">{facility.code}</span>
                      <Status value={facility.operational_status} />
                    </div>
                    <h3>{facility.name}</h3>
                    <p>{label(facility.facility_type)}</p>
                    <div className="card-bottom">
                      <span>{facility.location}</span>
                      <span aria-hidden="true">↗</span>
                    </div>
                  </Link>
                ))}
              </div>
            )}
            <Pager page={state.data.pagination} />
          </>
        )}
      </section>
      <p className="footnote">
        Select a facility to inspect its recorded equipment status.
      </p>
    </>
  );
}
function Equipment({
  facilityId,
  offset,
}: {
  facilityId: string;
  offset: number;
}) {
  const load = useCallback(
    (signal: AbortSignal) =>
      get(
        "/equipment-units",
        `/equipment-units?facility_id=${encodeURIComponent(facilityId)}&limit=${PAGE_SIZE}&offset=${offset}`,
        signal,
      ),
    [facilityId, offset],
  );
  const { state, retry } = useResource(load);
  return (
    <section className="panel" aria-labelledby="equipment-heading">
      <div className="panel-heading">
        <h2 id="equipment-heading">Equipment</h2>
        <span>Recorded units</span>
      </div>
      {state.status === "loading" && <Notice message="Loading equipment…" />}
      {state.status === "error" && (
        <Notice message={state.message} retry={retry} />
      )}
      {state.status === "ready" && (
        <>
          {state.data.items.length === 0 ? (
            <Notice
              message={
                state.data.pagination.total
                  ? "No equipment on this page. Use Previous to return."
                  : "No equipment is recorded at this facility."
              }
            />
          ) : (
            <ul className="equipment-list">
              {state.data.items.map((unit) => (
                <li key={unit.id}>
                  <div>
                    <strong>{unit.asset_tag}</strong>
                    <span className="record-id">Record {unit.id}</span>
                  </div>
                  <Status value={unit.operational_status} />
                </li>
              ))}
            </ul>
          )}
          <Pager page={state.data.pagination} />
        </>
      )}
    </section>
  );
}
function Facility({
  facilityId,
  offset,
}: {
  facilityId: string;
  offset: number;
}) {
  const load = useCallback(
    (signal: AbortSignal) =>
      get(
        "/facilities/{facility_id}",
        `/facilities/${encodeURIComponent(facilityId)}`,
        signal,
      ),
    [facilityId],
  );
  const { state, retry } = useResource(load);
  return (
    <>
      <Link className="back-link" to="/">
        <span aria-hidden="true">← </span>All facilities
      </Link>
      {state.status === "loading" && <Notice message="Loading facility…" />}
      {state.status === "error" && (
        <Notice message={state.message} retry={retry} />
      )}
      {state.status === "ready" && (
        <>
          <div className="page-heading">
            <div>
              <p className="eyebrow">FACILITY / {state.data.code}</p>
              <h1>{state.data.name}</h1>
              <p className="lede">
                {state.data.location} · {label(state.data.facility_type)}
              </p>
            </div>
            <Status value={state.data.operational_status} />
          </div>
          <Equipment
            key={`${facilityId}:${offset}`}
            facilityId={facilityId}
            offset={offset}
          />
        </>
      )}
    </>
  );
}
function OperationsRoute() {
  const { facilityId } = useParams();
  const offset = useOffset();
  if (offset === null)
    return (
      <>
        <h1>Invalid page</h1>
        <p>Choose a valid page from Operations.</p>
        <Link to="/">Return to Operations</Link>
      </>
    );
  return facilityId ? (
    <Facility key={facilityId} facilityId={facilityId} offset={offset} />
  ) : (
    <Facilities key={offset} offset={offset} />
  );
}
export function App() {
  const location = useLocation();
  const main = useRef<HTMLElement>(null);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    main.current?.focus();
  }, [location.pathname, location.search]);
  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link className="brand" to="/" aria-label="Space Corp home">
          <Brand />
        </Link>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          <NavLink
            to="/"
            className={({ isActive }) =>
              isActive || location.pathname.startsWith("/facilities/")
                ? "active"
                : ""
            }
            end
          >
            Operations <span aria-hidden="true">↗</span>
          </NavLink>
          <NavLink to="/ask">Ask a question</NavLink>
        </nav>
        <div className="sidebar-note">
          <span className="signal" aria-hidden="true" /> LOCAL DEMO
          <p>
            Ground stations. Orbital hubs. Lunar outposts. One Space Corp
            network.
          </p>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>Mission operations</span>
          <span className="environment">Synthetic workspace</span>
        </header>
        <main id="main" ref={main} tabIndex={-1}>
          <Routes>
            <Route path="/" element={<OperationsRoute />} />
            <Route
              path="/facilities/:facilityId"
              element={<OperationsRoute />}
            />
            <Route path="/ask" element={<QuestionScreen />} />
            <Route
              path="*"
              element={
                <>
                  <h1>Page not found</h1>
                  <Link to="/">Return to Operations</Link>
                </>
              }
            />
          </Routes>
        </main>
        <footer>
          SPACE CORP <span>Space Corp network · Read only</span>
        </footer>
      </div>
    </div>
  );
}

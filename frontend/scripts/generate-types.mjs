import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const root = fileURLToPath(new URL("../../", import.meta.url));
const schema = execFileSync(
  `${root}.venv/bin/python`,
  [
    "-c",
    'import json; from app.main import create_app; from app.config import Settings; print(json.dumps(create_app(Settings(_env_file=None, application_name="Agentic AI Operations Platform")).openapi(),sort_keys=True))',
  ],
  { cwd: root, encoding: "utf8" },
);
const digest = createHash("sha256").update(schema).digest("hex");
const output =
  "// Generated from FastAPI OpenAPI. Run pnpm types:generate; do not edit.\n" +
  astToString(await openapiTS(JSON.parse(schema)));
const target = new URL("../src/api/generated.d.ts", import.meta.url);
const provenance = new URL("../src/api/provenance.json", import.meta.url);
if (process.argv.includes("--check")) {
  const saved = JSON.parse(readFileSync(provenance, "utf8"));
  if (
    readFileSync(target, "utf8") !== output ||
    saved.schema_sha256 !== digest
  ) {
    throw new Error(
      "Backend contract changed. Run pnpm types:generate and review the diff.",
    );
  }
  console.log("Generated types match the backend contract.");
} else {
  writeFileSync(target, output);
  writeFileSync(
    provenance,
    JSON.stringify(
      {
        backend_revision: execFileSync("git", ["rev-parse", "HEAD"], {
          cwd: root,
          encoding: "utf8",
        }).trim(),
        schema_sha256: digest,
        source: "app.main.create_app().openapi()",
      },
      null,
      2,
    ) + "\n",
  );
}

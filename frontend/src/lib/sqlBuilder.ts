// Visual query model -> SQL. The generated SQL is shown (and editable) in the SQL editor; the
// backend runs it through the read-only session, so the builder needs no security logic.

export type Aggregate = "" | "count" | "count_distinct" | "sum" | "avg" | "min" | "max";
export type JoinType = "INNER" | "LEFT";
export type FilterOp =
  | "=" | "!=" | "<" | "<=" | ">" | ">="
  | "contains" | "starts" | "ends" | "between" | "in" | "null" | "notnull";

export interface QBTable {
  id: string; // alias, e.g. t1
  table: string;
  x: number;
  y: number;
}

export interface QBColumn {
  id: string;
  alias: string;
  column: string;
  agg: Aggregate;
  label: string;
}

export interface QBJoin {
  id: string;
  from: string; // table alias already in the query
  to: string;
  fromColumn: string;
  toColumn: string;
  type: JoinType;
}

export interface QBFilter {
  id: string;
  alias: string;
  column: string;
  op: FilterOp;
  value: string;
  value2: string;
}

export interface QBSort {
  id: string;
  alias: string;
  column: string;
  dir: "ASC" | "DESC";
}

export interface QueryModel {
  tables: QBTable[];
  columns: QBColumn[];
  joins: QBJoin[];
  filters: QBFilter[];
  sorts: QBSort[];
  distinct: boolean;
  limit: number | null;
}

export const emptyModel = (): QueryModel => ({
  tables: [],
  columns: [],
  joins: [],
  filters: [],
  sorts: [],
  distinct: false,
  limit: 1000,
});

export const quoteId = (s: string) => `"${s.replace(/"/g, '""')}"`;

function literal(v: string): string {
  const trimmed = v.trim();
  if (trimmed !== "" && /^-?\d+(\.\d+)?$/.test(trimmed)) return trimmed;
  return `'${v.replace(/'/g, "''")}'`;
}

function likeLiteral(v: string, before: string, after: string): string {
  const escaped = v.replace(/\\/g, "\\\\").replace(/%/g, "\\%").replace(/_/g, "\\_");
  return `'${before}${escaped.replace(/'/g, "''")}${after}' ESCAPE '\\'`;
}

const ref = (alias: string, column: string) => `${alias}.${quoteId(column)}`;

function columnExpr(c: QBColumn): string {
  const r = ref(c.alias, c.column);
  switch (c.agg) {
    case "count":
      return `count(${r})`;
    case "count_distinct":
      return `count(DISTINCT ${r})`;
    case "":
      return r;
    default:
      return `${c.agg}(${r})`;
  }
}

function filterExpr(f: QBFilter): string {
  const r = ref(f.alias, f.column);
  switch (f.op) {
    case "null":
      return `${r} IS NULL`;
    case "notnull":
      return `${r} IS NOT NULL`;
    case "contains":
      return `${r} LIKE ${likeLiteral(f.value, "%", "%")}`;
    case "starts":
      return `${r} LIKE ${likeLiteral(f.value, "", "%")}`;
    case "ends":
      return `${r} LIKE ${likeLiteral(f.value, "%", "")}`;
    case "between":
      return `${r} BETWEEN ${literal(f.value)} AND ${literal(f.value2)}`;
    case "in": {
      const items = f.value.split(",").map((x) => x.trim()).filter(Boolean).map(literal);
      return `${r} IN (${items.join(", ") || "NULL"})`;
    }
    default:
      return `${r} ${f.op} ${literal(f.value)}`;
  }
}

export interface BuildResult {
  sql: string;
  warnings: string[]; // i18n keys
}

export function buildSql(m: QueryModel): BuildResult {
  const warnings: string[] = [];
  if (!m.tables.length) return { sql: "", warnings: ["query.warn.noTables"] };
  const byId = new Map(m.tables.map((t) => [t.id, t]));
  const [first] = m.tables;
  const included = new Set([first.id]);
  const lines = [`FROM ${quoteId(first.table)} AS ${first.id}`];

  // add joined tables in a connected order, starting from the first table
  let progress = true;
  const pending = [...m.joins];
  while (progress && pending.length) {
    progress = false;
    for (let i = 0; i < pending.length; i++) {
      const j = pending[i];
      const fromIn = included.has(j.from);
      const toIn = included.has(j.to);
      if (fromIn === toIn) {
        if (fromIn) {
          // both already in: extra condition on an existing join
          lines.push(`  AND ${ref(j.from, j.fromColumn)} = ${ref(j.to, j.toColumn)}`);
          pending.splice(i--, 1);
          progress = true;
        }
        continue;
      }
      const [known, added, knownCol, addedCol] = fromIn
        ? [j.from, j.to, j.fromColumn, j.toColumn]
        : [j.to, j.from, j.toColumn, j.fromColumn];
      const table = byId.get(added);
      if (!table) continue;
      lines.push(
        `${j.type === "LEFT" ? "LEFT JOIN" : "JOIN"} ${quoteId(table.table)} AS ${added} ` +
          `ON ${ref(known, knownCol)} = ${ref(added, addedCol)}`,
      );
      included.add(added);
      pending.splice(i--, 1);
      progress = true;
    }
  }
  if (m.tables.some((t) => !included.has(t.id))) warnings.push("query.warn.unjoined");

  const cols = m.columns.filter((c) => included.has(c.alias));
  const names = cols.map((c) => c.label || c.column);
  const duplicated = new Set(names.filter((n, i) => names.indexOf(n) !== i));
  const select = cols.length
    ? cols.map((c) => {
        const alias =
          c.label ||
          (c.agg ? `${c.agg}_${c.column}` : duplicated.has(c.column) ? `${c.alias}_${c.column}` : "");
        return alias ? `${columnExpr(c)} AS ${quoteId(alias)}` : columnExpr(c);
      })
    : [`${first.id}.*`];
  if (!cols.length) warnings.push("query.warn.noColumns");

  const parts = [`SELECT ${m.distinct ? "DISTINCT " : ""}${select.join(",\n       ")}`, ...lines];
  const where = m.filters.filter((f) => included.has(f.alias) && f.column).map(filterExpr);
  if (where.length) parts.push(`WHERE ${where.join("\n  AND ")}`);
  const hasAgg = cols.some((c) => c.agg);
  const groupBy = cols.filter((c) => !c.agg).map((c) => ref(c.alias, c.column));
  if (hasAgg && groupBy.length) parts.push(`GROUP BY ${groupBy.join(", ")}`);
  const order = m.sorts
    .filter((s) => included.has(s.alias) && s.column)
    .map((s) => {
      const selected = cols.find((c) => c.alias === s.alias && c.column === s.column && c.agg);
      const expr = selected ? columnExpr(selected) : ref(s.alias, s.column);
      return `${expr} ${s.dir}`;
    });
  if (order.length) parts.push(`ORDER BY ${order.join(", ")}`);
  if (m.limit) parts.push(`LIMIT ${Math.max(1, Math.floor(m.limit))}`);
  return { sql: parts.join("\n"), warnings };
}

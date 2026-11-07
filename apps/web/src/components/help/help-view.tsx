import { CopyCommand } from "@/components/ui/copy-command";

const SETUP = [
  { step: "Install the API and web dependencies", command: "./scripts/dev.ps1 setup" },
  {
    step: "Create and start the database (once, then each session)",
    command: "./scripts/db.ps1 init",
  },
  { step: "Apply database migrations", command: "./scripts/dev.ps1 migrate" },
  { step: "Pull the local models (about 2.8 GB)", command: "ollama pull qwen3:4b" },
  { step: "", command: "ollama pull nomic-embed-text:v1.5" },
  { step: "Create the synthetic SQL demo database", command: "./scripts/dev.ps1 seed-demo" },
  { step: "Run the API, worker and web app (three terminals)", command: "./scripts/dev.ps1 api" },
  { step: "", command: "./scripts/dev.ps1 worker" },
  { step: "", command: "./scripts/dev.ps1 web" },
];

const TROUBLE: { problem: string; fix: string; command?: string }[] = [
  {
    problem: "Documents stay Queued",
    fix: "The ingestion worker isn't running. Start it in its own terminal.",
    command: "./scripts/dev.ps1 worker",
  },
  {
    problem: "“Cannot reach the local Ollama runtime”",
    fix: "Start Ollama (it usually runs as a desktop app or service).",
    command: "ollama serve",
  },
  {
    problem: "A model is “not installed”",
    fix: "Pull the exact tag shown on the Overview page. KnowFlow never downloads models itself.",
    command: "ollama pull qwen3:4b",
  },
  {
    problem: "“The database schema is not up to date”",
    fix: "Apply migrations after updating the code.",
    command: "./scripts/dev.ps1 migrate",
  },
  {
    problem: "Answers take a minute or more",
    fix: "Generation runs on this machine's CPU. On ~8 GB RAM, expect 30–90 s per answer; the first answer after a pause also loads the model. Close memory-heavy apps, or use qwen3:8b only on a 16 GB+ machine.",
  },
  {
    problem: "A PDF fails with “no text layer”",
    fix: "It's a scanned image. OCR isn't supported in v1; export a text-based PDF instead.",
  },
  {
    problem: "SQL Analyst says the demo database isn't set up",
    fix: "Set DEMO_DB_READER_PASSWORD in .env, then seed the demo and restart the API.",
    command: "./scripts/dev.ps1 seed-demo",
  },
];

/** Help: setup checklist, troubleshooting and what KnowFlow does with your data. */
export function HelpView() {
  return (
    <div className="flex max-w-[880px] flex-col gap-6">
      <header>
        <h1 className="text-[26px] leading-tight font-semibold tracking-tight">Help</h1>
        <p className="mt-1 max-w-prose text-[15px] text-muted-foreground">
          Everything runs on this machine: PostgreSQL, the API, a background worker and local models
          through Ollama. No account or API key is needed.
        </p>
      </header>

      <section aria-labelledby="setup" className="rounded-xl border bg-card px-5 py-5">
        <h2 id="setup" className="text-[18px] font-semibold tracking-tight">
          Setup checklist
        </h2>
        <p className="mt-1 text-[14px] text-muted-foreground">
          Windows PowerShell commands from the repository root. macOS/Linux use the same targets
          with <code className="font-mono">make</code>. See README.md for details.
        </p>
        <ol className="mt-3 flex flex-col gap-1">
          {SETUP.map((s, i) => (
            <li key={i}>
              {s.step && <p className="mt-2 text-[14px] font-medium">{s.step}</p>}
              <CopyCommand command={s.command} />
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="trouble" className="rounded-xl border bg-card px-5 py-5">
        <h2 id="trouble" className="text-[18px] font-semibold tracking-tight">
          Troubleshooting
        </h2>
        <dl className="mt-3 flex flex-col divide-y">
          {TROUBLE.map((t) => (
            <div key={t.problem} className="py-3">
              <dt className="text-[14px] font-medium">{t.problem}</dt>
              <dd className="mt-0.5 text-[14px] text-muted-foreground">{t.fix}</dd>
              {t.command && (
                <dd>
                  <CopyCommand command={t.command} />
                </dd>
              )}
            </div>
          ))}
        </dl>
        <p className="mt-3 text-[13px] text-muted-foreground">
          Every error shows a request ID. Search for it in the API terminal output, or open
          Activity.
        </p>
      </section>

      <section aria-labelledby="data" className="rounded-xl border bg-card px-5 py-5">
        <h2 id="data" className="text-[18px] font-semibold tracking-tight">
          Your data and the models
        </h2>
        <ul className="mt-3 flex list-disc flex-col gap-1.5 pl-5 text-[14px]">
          <li>
            Uploaded files stay in the local data folder under generated names; nothing is sent to a
            hosted service.
          </li>
          <li>
            Answers are written only from retrieved passages, and every citation is checked against
            them. If nothing supports an answer, KnowFlow says so.
          </li>
          <li>
            Text inside documents is treated as data: instructions hidden in a document are not
            followed.
          </li>
          <li>
            The SQL Analyst runs one validated SELECT with a read-only database user, a time limit
            and a row cap. It asks before guessing what a business term means.
          </li>
          <li>
            Logs and the activity record contain ids, counts and timings, never document text,
            questions or passwords.
          </li>
        </ul>
      </section>

      <section aria-labelledby="keys" className="rounded-xl border bg-card px-5 py-5">
        <h2 id="keys" className="text-[18px] font-semibold tracking-tight">
          Keyboard
        </h2>
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-[14px]">
          <dt className="font-mono">Tab</dt>
          <dd>Move between controls; the first Tab offers “Skip to content”.</dd>
          <dt className="font-mono">Ctrl+Enter</dt>
          <dd>Send a question in Ask KnowFlow or the SQL Analyst.</dd>
          <dt className="font-mono">Esc</dt>
          <dd>Close a drawer or dialog.</dd>
        </dl>
      </section>
    </div>
  );
}

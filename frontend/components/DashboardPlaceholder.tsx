type Stat = {
  label: string;
  value: string;
};

type Action = {
  title: string;
  description: string;
};

type DashboardPlaceholderProps = {
  role: string;
  title: string;
  description?: string;
  stats: Stat[];
  actions: Action[];
};

export function DashboardPlaceholder({
  role,
  title,
  description,
  stats,
  actions
}: DashboardPlaceholderProps) {
  return (
    <section className="mx-auto max-w-7xl px-5 py-10 sm:px-6 lg:py-14">
      <div className="flex flex-col gap-3">
        <p className="text-sm font-semibold uppercase tracking-wide text-emerald-700">
          {role} dashboard
        </p>
        <h1 className="text-3xl font-bold text-slate-950 sm:text-4xl">{title}</h1>
        {description ? (
          <p className="max-w-3xl text-base leading-7 text-slate-700">{description}</p>
        ) : null}
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <article key={stat.label} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-medium text-slate-600">{stat.label}</p>
            <p className="mt-3 text-3xl font-bold text-slate-950">{stat.value}</p>
          </article>
        ))}
      </div>

      <div className="mt-8 grid gap-4 lg:grid-cols-3">
        {actions.map((action) => (
          <article key={action.title} className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-950">{action.title}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-700">{action.description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

import { Elysia } from "elysia";
import { staticPlugin } from "@elysiajs/static";
import { SQL } from "bun";

const dbUrl = process.env.DATABASE_URL;
if (!dbUrl) throw new Error("DATABASE_URL is required");

const sql = new SQL({ url: dbUrl, max: 2, idleTimeout: 30 });

const app = new Elysia()
  .use(
    staticPlugin({
      assets: "public",
      prefix: "/",
      indexHTML: true,
    })
  )
  .get("/api/years", async () => {
    const currentYear = String(new Date().getFullYear());

    const rows = await sql`
      SELECT DISTINCT EXTRACT(YEAR FROM play_date)::int AS year
      FROM play_data
      ORDER BY year
    `;
    const years = rows
      .map((r: any) => String(r.year))
      .filter((y: string) => Number(y) <= Number(currentYear));

    if (!years.includes(currentYear)) years.push(currentYear);
    return years.sort();
  })
  .get("/api/play-data", async ({ query }: { query: Record<string, string | undefined> }) => {
    const year = query.year;
    const spillover = query.spillover === "1";

    let rows;
    if (year) {
      const yr = Number(year);
      if (spillover) {
        // Include Jan 1-7 of next year so the last week column of Dec renders fully
        rows = await sql`
          SELECT play_date, maimai_play_count, chunithm_play_count, maimai_rating, chunithm_rating
          FROM play_data
          WHERE play_date >= ${`${yr}-01-01`}::date
            AND play_date <= ${`${yr + 1}-01-07`}::date
          ORDER BY play_date
        `;
      } else {
        rows = await sql`
          SELECT play_date, maimai_play_count, chunithm_play_count, maimai_rating, chunithm_rating
          FROM play_data
          WHERE EXTRACT(YEAR FROM play_date) = ${yr}
          ORDER BY play_date
        `;
      }
    } else {
      rows = await sql`
        SELECT play_date, maimai_play_count, chunithm_play_count, maimai_rating, chunithm_rating
        FROM play_data
        ORDER BY play_date
      `;
    }
    return rows.map((r: any) => ({
      date:
        r.play_date instanceof Date
          ? r.play_date.toISOString().slice(0, 10)
          : String(r.play_date),
      maimai: r.maimai_play_count ?? 0,
      chunithm: r.chunithm_play_count ?? 0,
      maimai_rating: r.maimai_rating != null ? Number(r.maimai_rating) : null,
      chunithm_rating: r.chunithm_rating != null ? Number(r.chunithm_rating) : null,
    }));
  })
  .listen(3000);

console.log(`Dashboard running at http://localhost:${app.server!.port}`);

#!/usr/bin/env python3
# Applies the Luminos episode-picker change (DECISION 186) to a pristine seerr-3.4.1 tree.
# Usage: ep_patch.py <seerr-3.4.1 dir>
import os
import sys

ROOT = sys.argv[1]
TAG = "[CHANGE: cowork | 2026-11-13] Luminos episode picker (DECISION 186)."


def edit(rel, pairs):
    p = os.path.join(ROOT, rel)
    s = open(p, encoding="utf-8").read()
    for old, new, *cnt in pairs:
        n = s.count(old)
        want = cnt[0] if cnt else 1
        if want == "first":
            if n < 1:
                sys.exit("%s: anchor not found: %r" % (rel, old[:80]))
            s = s.replace(old, new, 1)
            continue
        if n != want:
            sys.exit("%s: anchor found %d times (want %d): %r" % (rel, n, want, old[:80]))
        s = s.replace(old, new)
    open(p, "w", encoding="utf-8").write(s)
    print("patched", rel)


def write(rel, body):
    p = os.path.join(ROOT, rel)
    open(p, "w", encoding="utf-8").write(body)
    print("created", rel)


# ------------------------------------------------------------------ entity
edit("server/entity/SeasonRequest.ts", [(
    """  @Column({ type: 'int', default: MediaRequestStatus.PENDING })
  public status: MediaRequestStatus;
""",
    """  @Column({ type: 'int', default: MediaRequestStatus.PENDING })
  public status: MediaRequestStatus;

  // %s
  // JSON array of the episode numbers to download for this season. null = the whole season.
  @Column({ type: 'text', nullable: true })
  public episodes?: string | null;
""" % TAG)])

# ------------------------------------------------------------------ body type
edit("server/interfaces/api/requestInterfaces.ts", [(
    """  seasons?: number[] | 'all';
  is4k?: boolean;""",
    """  seasons?: number[] | 'all';
  // %s season number -> episode numbers; a season left out = all episodes.
  episodes?: Record<string, number[]>;
  is4k?: boolean;""" % TAG)])

# ------------------------------------------------------------------ request creation
edit("server/entity/MediaRequest.ts", [
    ("@Entity()", """// %s
// Turns the picks for one season into what SeasonRequest.episodes stores. Anything empty,
// malformed or absent becomes null, which means "the whole season" -- the safe default.
const pickEpisodes = (
  picks: MediaRequestBody['episodes'],
  seasonNumber: number
): string | null => {
  const list = picks?.[String(seasonNumber)];
  if (!Array.isArray(list) || list.length === 0) {
    return null;
  }
  const clean = Array.from(
    new Set(
      list.map(Number).filter((n) => Number.isInteger(n) && n >= 0 && n < 10000)
    )
  ).sort((a, b) => a - b);
  return clean.length ? JSON.stringify(clean) : null;
};

@Entity()""" % TAG),
    ("""            new SeasonRequest({
              seasonNumber: sn,
              status: user.hasPermission(""",
     """            new SeasonRequest({
              seasonNumber: sn,
              episodes: pickEpisodes(requestBody.episodes, sn),
              status: user.hasPermission("""),
])

# ------------------------------------------------------------------ migrations
write("server/migration/sqlite/1794620000000-AddEpisodesToSeasonRequest.ts", """// %s
import type { MigrationInterface, QueryRunner } from 'typeorm';

export class AddEpisodesToSeasonRequest1794620000000 implements MigrationInterface {
  name = 'AddEpisodesToSeasonRequest1794620000000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(
      `ALTER TABLE "season_request" ADD COLUMN "episodes" text`
    );
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(
      `ALTER TABLE "season_request" DROP COLUMN "episodes"`
    );
  }
}
""" % TAG)
write("server/migration/postgres/1794620000000-AddEpisodesToSeasonRequest.ts", """// %s
import type { MigrationInterface, QueryRunner } from 'typeorm';

export class AddEpisodesToSeasonRequest1794620000000 implements MigrationInterface {
  name = 'AddEpisodesToSeasonRequest1794620000000';

  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`ALTER TABLE "season_request" ADD "episodes" text`);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(
      `ALTER TABLE "season_request" DROP COLUMN "episodes"`
    );
  }
}
""" % TAG)

# ------------------------------------------------------------------ subscriber -> sonarr
edit("server/subscriber/MediaRequestSubscriber.ts", [(
    """          seasons: entity.seasons.map((season) => season.seasonNumber),
          seasonFolder: sonarrSettings.enableSeasonFolders,""",
    """          seasons: entity.seasons.map((season) => season.seasonNumber),
          // %s
          episodes: entity.seasons.reduce<Record<number, number[]>>(
            (acc, season) => {
              if (season.episodes) {
                try {
                  const list = JSON.parse(season.episodes);
                  if (Array.isArray(list) && list.length) {
                    acc[season.seasonNumber] = list.map(Number);
                  }
                } catch {
                  // unreadable -> whole season, the safe default
                }
              }
              return acc;
            },
            {}
          ),
          seasonFolder: sonarrSettings.enableSeasonFolders,""" % TAG)])

# ------------------------------------------------------------------ sonarr api
edit("server/api/servarr/sonarr.ts", [
    ("""  seasons: number[];
  seasonFolder: boolean;""",
     """  seasons: number[];
  // %s season -> episode numbers to keep monitored. Absent = whole season.
  episodes?: Record<number, number[]>;
  seasonFolder: boolean;""" % TAG),
    ("""          if (options.searchNow) {
            this.searchSeries(newSeriesResponse.data.id);
          }""",
     """          // %s
          await this.applyEpisodePicks(
            newSeriesResponse.data.id,
            options.episodes,
            false
          );

          if (options.searchNow) {
            this.searchSeries(newSeriesResponse.data.id);
          }""" % TAG),
    ("""            searchForMissingEpisodes: options.searchNow,""",
     """            // %s With picks, Sonarr must not search on add: the
            // picks are applied first, then the search runs on what is left monitored.
            searchForMissingEpisodes:
              options.searchNow && !this.hasEpisodePicks(options.episodes),""" % TAG),
    ("""        logger.info('Sonarr accepted request', { label: 'Sonarr' });""",
     """        logger.info('Sonarr accepted request', { label: 'Sonarr' });
        // %s
        if (this.hasEpisodePicks(options.episodes)) {
          await this.applyEpisodePicks(
            createdSeriesResponse.data.id,
            options.episodes,
            true
          );
          if (options.searchNow) {
            this.searchSeries(createdSeriesResponse.data.id);
          }
        }""" % TAG),
    ("""  private buildSeasonList(""",
     """  // %s
  private hasEpisodePicks(picks?: Record<number, number[]>): boolean {
    return (
      !!picks &&
      Object.values(picks).some((list) => Array.isArray(list) && list.length > 0)
    );
  }

  public async unmonitorEpisodes(episodeIds: number[]): Promise<void> {
    await this.axios.put('/episode/monitor', {
      episodeIds,
      monitored: false,
    });
  }

  // Leave only the picked episodes monitored in each picked season.
  // A series Sonarr has only just added fills its episode list from a background refresh,
  // so wait for it, and re-apply a few times afterwards: Sonarr's own post-add step can
  // still set monitored flags once the refresh finishes. Every pass is idempotent.
  private async applyEpisodePicks(
    seriesId: number | undefined,
    picks: Record<number, number[]> | undefined,
    justAdded: boolean
  ): Promise<void> {
    if (!seriesId || !picks || !this.hasEpisodePicks(picks)) {
      return;
    }
    const seasons = Object.keys(picks).map(Number);
    const sleep = (ms: number) =>
      new Promise((resolve) => setTimeout(resolve, ms));
    const pass = async (): Promise<boolean> => {
      const episodes = await this.getEpisodes(seriesId);
      const inSeasons = episodes.filter((ep) =>
        seasons.includes(ep.seasonNumber)
      );
      if (inSeasons.length === 0) {
        return false;
      }
      const wanted = (ep: EpisodeResult) =>
        (picks[ep.seasonNumber] || []).includes(ep.episodeNumber);
      const drop = inSeasons
        .filter((ep) => ep.monitored && !wanted(ep))
        .map((ep) => ep.id);
      const keep = inSeasons
        .filter((ep) => !ep.monitored && wanted(ep))
        .map((ep) => ep.id);
      if (drop.length) {
        await this.unmonitorEpisodes(drop);
      }
      if (keep.length) {
        await this.monitorEpisodes(keep);
      }
      logger.info('Applied episode picks', {
        label: 'Sonarr',
        seriesId,
        unmonitored: drop.length,
        monitored: keep.length,
        picks,
      });
      return true;
    };

    let applied = false;
    for (let attempt = 0; attempt < (justAdded ? 40 : 3) && !applied; attempt++) {
      try {
        applied = await pass();
      } catch (e) {
        logger.warn('Failed to apply episode picks, retrying', {
          label: 'Sonarr',
          seriesId,
          errorMessage: e.message,
        });
      }
      if (!applied) {
        await sleep(3000);
      }
    }
    if (!applied) {
      logger.error('Gave up applying episode picks', {
        label: 'Sonarr',
        seriesId,
        picks,
      });
      return;
    }
    if (justAdded) {
      for (const wait of [10000, 20000, 30000]) {
        await sleep(wait);
        try {
          await pass();
        } catch (e) {
          logger.warn('Episode picks re-check failed', {
            label: 'Sonarr',
            seriesId,
            errorMessage: e.message,
          });
        }
      }
    }
  }

  private buildSeasonList(""" % TAG),
])

# ------------------------------------------------------------------ OpenAPI (document the field)
edit("seerr-api.yml", [(
    """                    - type: string
                      enum: [all]
                is4k:""",
    """                    - type: string
                      enum: [all]
                episodes:
                  type: object
                  description: Luminos episode picker. Season number -> episode numbers to download. A season left out gets all its episodes.
                  additionalProperties:
                    type: array
                    items:
                      type: number
                      minimum: 0
                is4k:""", "first")])

# ------------------------------------------------------------------ the request screen
edit("src/components/RequestModal/TvRequestModal.tsx", [
    ("import { useState } from 'react';", "import { Fragment, useState } from 'react';"),
    ("interface RequestModalProps extends React.HTMLAttributes<HTMLDivElement> {",
     """// %s
// The optional "All episodes" picker under a season. Ignoring it keeps today's behaviour
// (whole season). `picked` undefined = all; [] = none (the season is then left out).
interface PickerSeason {
  episodes: { episodeNumber: number; name: string }[];
}

const EpisodePicker = ({
  tmdbId,
  seasonNumber,
  picked,
  onChange,
}: {
  tmdbId: number;
  seasonNumber: number;
  picked?: number[];
  onChange: (list: number[] | null) => void;
}) => {
  const { data, error } = useSWR<PickerSeason>(
    `/api/v1/tv/${tmdbId}/season/${seasonNumber}`
  );
  if (error) {
    return (
      <div className="text-sm text-red-400">
        Could not load the episode list.
      </div>
    );
  }
  if (!data) {
    return <div className="text-sm text-gray-400">Loading episodes…</div>;
  }
  const all = data.episodes.map((e) => e.episodeNumber);
  const sel = new Set(picked ?? all);
  const update = (next: Set<number>) =>
    onChange(next.size === all.length ? null : all.filter((n) => next.has(n)));
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-4 text-xs text-gray-400">
        <span>Pick episodes. Leave them all ticked to get the whole season.</span>
        <button
          type="button"
          className="text-indigo-300 hover:text-indigo-200"
          onClick={() => onChange(null)}
        >
          All
        </button>
        <button
          type="button"
          className="text-indigo-300 hover:text-indigo-200"
          onClick={() => onChange([])}
        >
          None
        </button>
      </div>
      <div className="grid gap-1 sm:grid-cols-2">
        {data.episodes.map((e) => (
          <label
            key={e.episodeNumber}
            className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm text-gray-200 hover:bg-gray-700"
          >
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-gray-500 text-indigo-600"
              checked={sel.has(e.episodeNumber)}
              onChange={() => {
                const next = new Set(sel);
                if (next.has(e.episodeNumber)) {
                  next.delete(e.episodeNumber);
                } else {
                  next.add(e.episodeNumber);
                }
                update(next);
              }}
            />
            <span className="w-9 tabular-nums text-gray-400">
              E{e.episodeNumber}
            </span>
            <span className="truncate">{e.name}</span>
          </label>
        ))}
      </div>
    </div>
  );
};

interface RequestModalProps extends React.HTMLAttributes<HTMLDivElement> {""" % TAG),
    ("  const { data: quota } = useSWR<QuotaResponse>(",
     """  // %s Only seasons the user narrowed down are in here.
  const [pickedEpisodes, setPickedEpisodes] = useState<
    Record<number, number[]>
  >({});
  const [openPicker, setOpenPicker] = useState<number | null>(null);

  const { data: quota } = useSWR<QuotaResponse>(""" % TAG),
    ("      const response = await axios.post<MediaRequest>('/api/v1/request', {",
     """      // %s
      const seasonsToSend = settings.currentSettings.partialRequestsEnabled
        ? selectedSeasons.sort((a, b) => a - b)
        : getAllSeasons().filter(
            (season) => !getAllRequestedSeasons().includes(season)
          );
      // A season narrowed down to zero episodes is left out of the request.
      const finalSeasons = seasonsToSend.filter(
        (sn) => !(pickedEpisodes[sn] && pickedEpisodes[sn].length === 0)
      );
      if (finalSeasons.length === 0) {
        addToast('Pick at least one episode.', {
          appearance: 'error',
          autoDismiss: true,
        });
        return;
      }
      const episodePicks = Object.fromEntries(
        finalSeasons
          .filter((sn) => pickedEpisodes[sn]?.length)
          .map((sn) => [String(sn), pickedEpisodes[sn]])
      );
      const response = await axios.post<MediaRequest>('/api/v1/request', {""" % TAG),
    ("""        seasons: settings.currentSettings.partialRequestsEnabled
          ? selectedSeasons.sort((a, b) => a - b)
          : getAllSeasons().filter(
              (season) => !getAllRequestedSeasons().includes(season)
            ),
        ...overrideParams,""",
     """        seasons: finalSeasons,
        ...(Object.keys(episodePicks).length ? { episodes: episodePicks } : {}),
        ...overrideParams,"""),
    ("""                        <tr key={`season-${season.id}`}>""",
     """                        <Fragment key={`season-${season.id}`}>
                        <tr>"""),
    ("""                          </td>
                        </tr>
                      );
                    })}
                </tbody>""",
     """                            {/* %s */}
                            {!editRequest &&
                              !mediaSeason &&
                              !seasonRequest &&
                              (!settings.currentSettings.partialRequestsEnabled ||
                                isSelectedSeason(season.seasonNumber)) && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    setOpenPicker(
                                      openPicker === season.seasonNumber
                                        ? null
                                        : season.seasonNumber
                                    )
                                  }
                                  className={`ml-2 rounded-md border px-2 py-0.5 text-xs ${
                                    pickedEpisodes[season.seasonNumber]
                                      ? 'border-indigo-500 bg-indigo-900/60 text-indigo-100'
                                      : 'border-gray-600 text-gray-300 hover:border-gray-400'
                                  }`}
                                >
                                  {pickedEpisodes[season.seasonNumber]
                                    ? `${pickedEpisodes[season.seasonNumber].length} of ${season.episodeCount} eps`
                                    : 'All episodes'}{' '}
                                  {openPicker === season.seasonNumber ? '▴' : '▾'}
                                </button>
                              )}
                          </td>
                        </tr>
                        {openPicker === season.seasonNumber &&
                          !editRequest &&
                          !mediaSeason &&
                          !seasonRequest &&
                          (!settings.currentSettings.partialRequestsEnabled ||
                            isSelectedSeason(season.seasonNumber)) && (
                            <tr>
                              <td colSpan={4} className="bg-gray-800/60 px-4 py-3">
                                <EpisodePicker
                                  tmdbId={tmdbId}
                                  seasonNumber={season.seasonNumber}
                                  picked={pickedEpisodes[season.seasonNumber]}
                                  onChange={(list) =>
                                    setPickedEpisodes((prev) => {
                                      const next = { ...prev };
                                      if (list === null) {
                                        delete next[season.seasonNumber];
                                      } else {
                                        next[season.seasonNumber] = list;
                                      }
                                      return next;
                                    })
                                  }
                                />
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                </tbody>""" % TAG),
])
print("ALL OK")

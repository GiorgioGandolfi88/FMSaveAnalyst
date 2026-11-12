# fmsave record types (generated)

fmsave 0.12.2, OUTPUT_SCHEMA_VERSION=4

## Ability

A player's current and potential ability.

| field | type | status | description |
|---|---|---|---|
| current | `int` | unconfirmed | Current ability (unconfirmed). |
| potential | `int \| None` | unconfirmed | Potential ability, or None when the save stores a range code instead (unconfirmed). |
| potential_range_code | `int \| None` | unconfirmed | The stored negative code when potential is unknown, else None (unconfirmed). |

## AffiliateGroup

One stored group of clubs, with its members resolved to clubs where they resolve.

| field | type | status | description |
|---|---|---|---|
| group_index | `int` | verified | The group's own place in the section, counting from zero in stored order. It is fmsave's own index and not a value the save keeps: the groups carry no id of their own. |
| club_uids | `tuple[int \| None, ...]` | unconfirmed | Uid of each member, in stored order, None for a member whose stored club index no club record claims, which is about one member in sixty (unconfirmed). |
| club_names | `tuple[str \| None, ...]` | unconfirmed | Denormalised full name of each entry of `club_uids`, aligned with it and None wherever that uid is (unconfirmed). |

## Attributes

52 non-foot player attributes, shared by the display and raw scales.

| field | type | status | description |
|---|---|---|---|
| crossing | `int` | verified | Crossing. |
| dribbling | `int` | verified | Dribbling. |
| finishing | `int` | verified | Finishing. |
| heading | `int` | verified | Heading. |
| long_shots | `int` | verified | Long shots. |
| marking | `int` | verified | Marking. |
| off_the_ball | `int` | verified | Off the ball movement. |
| passing | `int` | verified | Passing. |
| penalty_taking | `int` | verified | Penalty taking. |
| tackling | `int` | verified | Tackling. |
| vision | `int` | verified | Vision. |
| handling | `int` | verified | Goalkeeping handling. |
| aerial_reach | `int` | verified | Goalkeeping aerial reach. |
| command_of_area | `int` | verified | Goalkeeping command of area. |
| communication | `int` | verified | Goalkeeping communication. |
| kicking | `int` | verified | Goalkeeping kicking. |
| throwing | `int` | verified | Goalkeeping throwing. |
| anticipation | `int` | verified | Anticipation. |
| decisions | `int` | verified | Decisions. |
| one_on_ones | `int` | verified | Goalkeeping one-on-ones. |
| positioning | `int` | verified | Positioning (an attribute, not a position rating). |
| reflexes | `int` | verified | Goalkeeping reflexes. |
| first_touch | `int` | verified | First touch. |
| technique | `int` | verified | Technique. |
| flair | `int` | verified | Flair. |
| corners | `int` | verified | Corners. |
| teamwork | `int` | verified | Teamwork. |
| work_rate | `int` | verified | Work rate. |
| long_throws | `int` | verified | Long throws. |
| eccentricity | `int` | verified | Goalkeeping eccentricity. |
| rushing_out | `int` | verified | Goalkeeping tendency to rush out. |
| punching | `int` | verified | Goalkeeping tendency to punch crosses. |
| acceleration | `int` | verified | Acceleration. |
| free_kick_taking | `int` | verified | Free kick taking. |
| strength | `int` | verified | Strength. |
| stamina | `int` | verified | Stamina. |
| pace | `int` | verified | Pace. |
| jumping_reach | `int` | verified | Jumping reach. |
| leadership | `int` | verified | Leadership. |
| dirtiness | `int` | verified | Dirtiness, a hidden attribute. |
| balance | `int` | verified | Balance. |
| bravery | `int` | verified | Bravery. |
| consistency | `int` | verified | Consistency, a hidden attribute. |
| aggression | `int` | verified | Aggression. |
| agility | `int` | verified | Agility. |
| important_matches | `int` | verified | Big-match temperament, a hidden attribute. |
| injury_proneness | `int` | verified | Injury proneness, a hidden attribute. |
| versatility | `int` | verified | Versatility, a hidden attribute. |
| natural_fitness | `int` | verified | Natural fitness. |
| determination | `int` | verified | Determination. |
| composure | `int` | verified | Composure. |
| concentration | `int` | verified | Concentration. |

## Clause

One clause attached to a contract, such as a release fee, an extension option or a bonus.

| field | type | status | description |
|---|---|---|---|
| kind | `common.CodedValue[contracts.ClauseKind]` | verified | The clause's kind. |
| parameter | `int \| None` | unconfirmed | The clause's parameter, whose meaning depends on kind; None when the save stores no parameter (unconfirmed). |
| value | `int \| None` | verified | The clause's money value, in the save's own money unit and not converted; None when the save stores no value. |

## Club

A club from the save's game database.

| field | type | status | description |
|---|---|---|---|
| uid | `int` | unconfirmed | fmsave's join key for this club within the save. The value 0 is valid. Use unique_id to match clubs across careers (unconfirmed). |
| name | `str` | unconfirmed | Full club name (unconfirmed). |
| short_name | `str` | unconfirmed | Short club name (unconfirmed). |
| nation_id | `int \| None` | unconfirmed | Save-local id of the nation whose league the club plays in, or None when the game stores no such nation, as for some school, university and amateur clubs (unconfirmed). |
| fa_nation_id | `int` | unconfirmed | Save-local id of the nation whose football association the club belongs to. It differs from nation_id for a club that plays in another nation's league, and is stored even where nation_id is None (unconfirmed). |
| city_id | `int \| None` | unconfirmed | Id of the club's city, or None when the save stores the missing-id marker instead (unconfirmed). |
| teams | `tuple[clubs.Team, ...]` | unconfirmed | The club's own teams in stored order, including slots no player is registered with, then the teams of the affiliate clubs it controls; an empty tuple when the team list cannot be read (unconfirmed). |
| parent_club_uid | `int \| None` | unconfirmed | Uid of the club that controls this one, when another club lists one of this club's teams among its affiliate teams, else None (unconfirmed). |
| parent_club_name | `str \| None` | unconfirmed | Denormalised full name of parent_club_uid; None wherever parent_club_uid is (unconfirmed). |
| reputation | `int \| None` | verified | Club reputation from 1 to 10000, or None when it cannot be read. |
| last_league_position | `int \| None` | verified | League position at the end of the last completed season, or None when it cannot be read. It is not the position in the current table. |
| unique_id | `int \| None` | unconfirmed | The club's Unique ID in the game database, for matching across separate careers. None when it cannot be read (unconfirmed). |
| gender | `Optional[common.CodedValue[clubs.ClubGender]]` | unconfirmed | The club's stored gender code, or None when no team list parses. Unknown codes keep their raw value (unconfirmed). |

## ClubFacilities

One club's facility ratings, as its own record stores them.

| field | type | status | description |
|---|---|---|---|
| club_uid | `int` | unconfirmed | Uid of the club (unconfirmed). |
| club_name | `str` | unconfirmed | Denormalised full name of club_uid (unconfirmed). |
| corporate_facilities | `common.CodedValue[facilities.CorporateFacilities]` | verified | How good the club's corporate facilities are. Every code from 0 to 20 carries a word, and a code outside that range is UNKNOWN with the raw number kept. A club that stores no rating reads NONE with raw 0, as its screen shows. |

## CodedValue

A number the save uses as a code, with its label.

| field | type | status | description |
|---|---|---|---|
| label | `EnumT` |  | The enum member for the code, or UNKNOWN. |
| raw | `int` |  | The number exactly as stored in the save. |

## Competition

One competition, as the stage table names it.

| field | type | status | description |
|---|---|---|---|
| id | `int` | verified | The competition id, in the stage id space, which `Suspension.competition_id` also uses. |
| database_id | `int \| None` | unconfirmed | The competition's id in the game's own editor database, which is stable across saves and is what an external name source is keyed on; None when the save holds no such link (unconfirmed). |
| name | `str \| None` | unconfirmed | The competition's name, which is None unless a name map is supplied: the save stores no competition names, and fmsave ships none (unconfirmed). |
| stage_ids | `tuple[int, ...]` | verified | The ids of this competition's stages, in the order the stage table stores them, which is ascending on every save seen. |

## CompetitionRules

One competition-rules block: promotion and relegation, prize money and the calendar.

| field | type | status | description |
|---|---|---|---|
| kind | `<enum 'RulesBlockKind'>` | unconfirmed | Which structure the row was read from. Every row is PREAMBLE, since the tagged rules groups are not read (unconfirmed). |
| competition_id | `int \| None` | unconfirmed | The competition of the league table the save stores right after this block, in the stage id space; None where that run is not exactly one table with a competition of its own, which is 32% to 45% of rows. Not a stored link: a position in the span, resolved through a vote on the fixture calendar (unconfirmed). |
| competition_name | `str \| None` | unconfirmed | Denormalised name of competition_id, which is None unless a name map is supplied, because the save stores no competition names (unconfirmed). |
| fixtures_per_club | `int \| None` | unconfirmed | How many matches each club plays, which is the number of rounds the block holds; None when no round decoded (unconfirmed). |
| promotion_places | `int \| None` | unconfirmed | How many clubs are promoted, or None when the block's two copies of the promotion quad differ (unconfirmed). |
| playoff_places | `int \| None` | unconfirmed | How many clubs enter a promotion play-off, or None as promotion_places (unconfirmed). |
| relegation_places | `int \| None` | unconfirmed | How many clubs are relegated, or None as promotion_places (unconfirmed). |
| prize_money | `tuple[int, ...]` | unconfirmed | Prize money by finishing position, in the save's base currency, in finishing order. Empty on most blocks: only about one block in eight carries a prize list at all (unconfirmed). |
| rounds | `tuple[rules.RulesRound, ...]` | unconfirmed | The competition's calendar, in stored order (unconfirmed). |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning. "promotion_byte2" is the third byte of the promotion quad. "tie_break_00" to "tie_break_15" are the tie-break codes the block lists, in order, and are absent past the end of that list; no displayed label names any of them, so they ship as raw numbers (unconfirmed). |

## Contract

A player's contract as it stands at the save's in-game date.

| field | type | status | description |
|---|---|---|---|
| player_uid | `int` | unconfirmed | Uid of the player this contract belongs to (unconfirmed). |
| player_name | `str \| None` | unconfirmed | Denormalised name of player_uid (unconfirmed). |
| club_uid | `int \| None` | unconfirmed | Uid of the contracting club of the record in effect, or None when no record is in effect or its team does not resolve (unconfirmed). |
| club_name | `str \| None` | unconfirmed | Denormalised name of club_uid (unconfirmed). |
| team_id | `int \| None` | unconfirmed | Id of the contracting team of the record in effect, or None (unconfirmed). |
| wage | `int \| None` | unconfirmed | Weekly wage from the record in effect, in the save's base currency (unconfirmed). |
| start | `datetime.date \| None` | unconfirmed | Contract start date, from the record in effect (unconfirmed). |
| end | `datetime.date \| None` | verified | Contract end date. |
| end_source | `<enum 'ContractEndSource'>` | verified | Where end was read from. |
| squad_status | `Optional[common.CodedValue[contracts.SquadStatus]]` | verified | Squad status from the terms of the record in effect, the role agreed in the contract rather than how much the player plays, or None when that record gives no terms up. |
| kind | `Optional[common.CodedValue[contracts.ContractType]]` | verified | The contract's type from the terms of the record in effect, or None when it gives no terms up. |
| clauses | `tuple[contracts.Clause, ...]` | verified | Clauses from the terms of the record in effect, or () when it gives no terms up. |
| on_loan | `bool \| None` | verified | Whether the player is on loan from the club of the contract in effect: True when he is registered with another club's team and the save holds a loan for him there that has not ended, False when it does not, and None when his club or the contract in effect is unknown. A player registered with a team his own club controls, such as a B team, is a player of that club, not on loan. |
| loan_parent_club_uid | `int \| None` | unconfirmed | Uid of the club of the contract in effect when on_loan is True, else None. It is club_uid under another name, so it carries the same status (unconfirmed). |
| loan_parent_club_name | `str \| None` | unconfirmed | Denormalised name of loan_parent_club_uid (unconfirmed). |
| loan_start | `datetime.date \| None` | verified | Date the loan began when on_loan is True, else None. It is also None when the loan's stored start does not decode as a game date, which keeps an unreadable start from costing the player his loan; no save read so far holds such a loan. |
| loan_end | `datetime.date \| None` | verified | Date the loan ends when on_loan is True, else None. |
| event_count | `int \| None` | unconfirmed | Contract event count from the terms of the record in effect, or None (unconfirmed). |
| chain | `tuple[contracts.ContractChainEntry, ...]` | unconfirmed | Every chain record, oldest first (unconfirmed). |
| chain_club_uids | `tuple[int \| None, ...]` | unconfirmed | Uid of the contracting club for each chain record, in the same order as chain; None where the team does not resolve (unconfirmed). |
| chain_club_names | `tuple[str \| None, ...]` | unconfirmed | Denormalised names for chain_club_uids, in the same order (unconfirmed). |
| chain_club_uids_with_terms | `tuple[int, ...]` | unconfirmed | Uids of the clubs of the chain records that carry their agreed terms and whose team resolves, in chain order (unconfirmed). |
| chain_club_names_with_terms | `tuple[str \| None, ...]` | unconfirmed | Denormalised names for chain_club_uids_with_terms, in the same order (unconfirmed). |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning, from the terms of the record in effect; a key is present only when its value was read (unconfirmed). |

## ContractChainEntry

One record in a player's registration chain.

| field | type | status | description |
|---|---|---|---|
| club_uid | `int \| None` | unconfirmed | Uid of the contracting club, or None when the team does not resolve (unconfirmed). |
| club_name | `str \| None` | unconfirmed | Denormalised name of club_uid (unconfirmed). |
| team_id | `int` | unconfirmed | Id of the contracting team, exactly as stored (unconfirmed). |
| wage | `int` | unconfirmed | Weekly wage, in the save's base currency (unconfirmed). |
| start | `datetime.date \| None` | unconfirmed | Start date of this spell (unconfirmed). |
| end | `datetime.date \| None` | verified | End date from this record's own terms, or None when it gives no terms up or stores no end. |
| has_terms | `bool` | unconfirmed | Whether this record carries the terms agreed in it: an end date, a squad status, a contract type and the clauses. A record that does not is still a spell at a club, with its wage and its start date (unconfirmed). |

## FinanceMonth

One club's money in one month.

| field | type | status | description |
|---|---|---|---|
| club_uid | `int` | unconfirmed | Uid of the club (unconfirmed). |
| club_name | `str` | unconfirmed | Denormalised full name of club_uid (unconfirmed). |
| month | `date` | verified | First day of the month the row covers, worked out from the save's own date: the last row of a club is the month before the save's month, and a club's two oldest rows landed on the months its own finance screen labelled them with. |
| balance | `int` | verified | The club's balance at the end of the month. On most clubs whose series begins with the career, the oldest row instead holds the balance before that month's net: the next row's balance adds both months' nets to it. |
| transfer_budget_allocated | `int` | unconfirmed | A transfer figure with no confirmed meaning (unconfirmed). It is **not** the budget the board allocated: a club's own finances screen showed a budget well above this figure with almost none of it spent, and this figure is below transfer_budget_remaining on about a quarter of rows. |
| transfer_budget_remaining | `int` | verified | What is left of the transfer budget. |
| wage_budget_weekly | `int` | verified | The wage budget, per week; a club's screen showed this times 52. |
| wage_payroll_weekly | `int` | verified | The wages being paid, per week; likewise times 52 on the screen. |
| income_excluding_transfers | `int` | unconfirmed | The month's income other than transfer fees (unconfirmed). |
| net_transfers | `int` | unconfirmed | The month's transfer flow, **positive for a net spend** (unconfirmed). |
| wage_bill | `int` | unconfirmed | The month's wage expenditure (unconfirmed). |
| net | `int` | verified | The month's income less its expenditure. |
| expenditure_excluding_transfers | `int` | unconfirmed | The month's expenditure other than transfer fees (unconfirmed). |
| total_income | `int` | unconfirmed | The month's total income (unconfirmed). |
| total_expenditure | `int` | unconfirmed | The month's total expenditure (unconfirmed). |

## Fixture

One match in the save's fixture calendar.

| field | type | status | description |
|---|---|---|---|
| stage_id | `int \| None` | verified | The stage this match belongs to, which is the only route to its competition; None when the record stores no stage. |
| competition_id | `int \| None` | verified | Id of the competition, in the **stage** id space, reached through the stage; None when the record has no stage, the stage is not in the stage table, or the stage names no competition. |
| competition_name | `str \| None` | unconfirmed | Denormalised name of competition_id, which is None unless a name map is supplied, because the save stores no competition names (unconfirmed). |
| round | `Optional[common.CodedValue[competitions.CompetitionRound]]` | verified | The stage's round, or None when the match has no stage or its stage carries no round, as a league matchday and a league phase do not. Codes with no confirmed meaning keep their raw number and are labelled UNKNOWN. |
| round_index | `int \| None` | verified | The match's zero-based index within its round, so a matchday is this plus one; None when the record stores the no-round value. |
| date | `datetime.date \| None` | verified | The kick-off date, or None when the stored date does not decode. |
| kick_off_time | `datetime.time \| None` | verified | The kick-off time of day, or None when the stored slot does not land inside a day. |
| season_start_year | `int \| None` | verified | The calendar year the season started in, or None when the record stores none, as some friendlies do. |
| home_team_id | `int` | verified | The home side's team id, exactly as stored. |
| home_club_uid | `int \| None` | verified | Uid of the club fielding the home team, or None when no club lists that team. |
| home_club_name | `str \| None` | verified | Denormalised name of home_club_uid, or None when the team does not resolve. |
| home_club_short_name | `str \| None` | verified | Denormalised short name of home_club_uid, or None when the team does not resolve. |
| home_team_slot | `int \| None` | verified | The home team's slot in its club's team list, 0 for the first entry, or None when the team does not resolve. |
| away_team_id | `int` | verified | The away side's team id, exactly as stored. |
| away_club_uid | `int \| None` | verified | Uid of the club fielding the away team, or None when no club lists that team. |
| away_club_name | `str \| None` | verified | Denormalised name of away_club_uid, or None when the team does not resolve. |
| away_club_short_name | `str \| None` | verified | Denormalised short name of away_club_uid, or None when the team does not resolve. |
| away_team_slot | `int \| None` | verified | The away team's slot in its club's team list, 0 for the first entry, or None when the team does not resolve. |
| home_goals | `int \| None` | verified | Goals the home side scored, or None when no unambiguous score was decoded. Empty goals on a played match do not mean it finished goalless. Score coverage varies between saves. |
| away_goals | `int \| None` | verified | Goals the away side scored, or None when no unambiguous score was decoded, as for home_goals. |
| played | `bool` | verified | Whether the save marks the match as played. |
| is_neutral_venue | `bool \| None` | verified | Whether the match was played away from the home club's usual grounds. A team's usual ground is the one it used most at home in this season, and each of the club's teams has its own, so a reserve side's ground counts too. False when the match is at a usual ground of any of the club's teams, True when it is not and the home team has a usual ground, and None when the ground is unknown or the home team played too few home matches this season to say. This is about the ground and not about which club counts as the home one: the home club is `home_team_id` whether the ground is neutral or not, and `LeagueTableMatch.home_or_away` is the field that says which side of a match a club was. The season is the stored season_start_year, which some friendlies leave empty, and every such match a team played shares one vote; a team that moved ground mid-career therefore has its earlier seasonless matches judged against the later ground. |
| stadium_uid | `int \| None` | unconfirmed | Uid of the ground the match is played at, from the stadium table; None when the record stores no ground or one the table does not hold. The join itself is exact, but a stadium uid is not confirmed by any displayed label, so this field can be no stronger than the uid it carries (unconfirmed). |
| stadium_name | `str \| None` | unconfirmed | Denormalised name of stadium_uid. Only a couple of hundred grounds store a name, so this is None on nearly every match even where stadium_uid is filled in; `Stadium.name` says why (unconfirmed). |
| referee_id | `int \| None` | verified | Save-local ID of the referee for a played match, or None when unavailable. Join to `Official.referee_id` from `Save.officials()`. |
| match_rules_template | `tuple[int, ...]` | unconfirmed | The three bytes naming the shared match-rules template this match uses. It is a template many competitions share and is **never** a competition id (unconfirmed). |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning. "result_r22" is the byte stored beside a stage-keyed result. A score recovered only from a match summary or calendar packet carries no such byte (unconfirmed). |

## GateResult

One reader check: an observed count or rate compared with its bounds.

| field | type | status | description |
|---|---|---|---|
| name | `str` |  | The check's name. |
| observed | `float \| None` |  | The observed count, rate or median, or None when a rate has no denominator. |
| minimum | `float \| None` |  | The lowest value that passes, or None when there is no lower bound. |
| maximum | `float \| None` |  | The highest value that passes, or None when there is no upper bound. |
| passed | `bool` |  | Whether the check passed; a check that was not applied always passes. |
| applied | `bool` |  | Whether the check could be evaluated. False for undersized sections, empty optional populations, or an unavailable prerequisite such as the save clock. |

## InjuryRecord

One injury the save remembers, of either kind.

| field | type | status | description |
|---|---|---|---|
| kind | `<enum 'InjuryRecordKind'>` | verified | Which store the row came from: HISTORY for an injury that happened, TYPED for a row carrying an injury type. |
| player_uid | `int \| None` | unconfirmed | Uid of the person the row is stored against, or None when the save no longer keeps that person as a player, which is about one HISTORY row in twenty (unconfirmed). |
| player_name | `str \| None` | unconfirmed | Denormalised display name of player_uid; None wherever player_uid is (unconfirmed). |
| date | `datetime.date \| None` | verified | When the injury happened, on a HISTORY row. On a TYPED row it is the day the player is expected back rather than the day he was hurt, which is why it is often ahead of the in-game date; it is None when the save stores no date at all. |
| team_id | `int \| None` | verified | Id of the team the person was registered with at the time, on a HISTORY row; None on every TYPED row, which carries no team. |
| club_uid | `int \| None` | verified | Uid of the club that fields team_id, which for a team another club controls is the controlling club; None when no club lists that team and on every TYPED row. |
| club_name | `str \| None` | verified | Denormalised full name of club_uid; None wherever club_uid is. |
| team_slot | `int \| None` | unconfirmed | The team's slot in club_uid's team list, counting that club's own teams first and then the teams it controls; None wherever club_uid is (unconfirmed). |
| type_id | `int \| None` | verified | The injury's type code, on a TYPED row; None on every HISTORY row, which carries no type. |
| type_name | `str \| None` | unconfirmed | Denormalised name of type_id from `Save.injury_types`, None for the codes that table has no entry for and on every row of a save with no per-match file (unconfirmed). |
| cause | `Optional[common.CodedValue[injuries.InjuryCause]]` | verified | Whether the injury happened in training or in a match, on a HISTORY row; None on every TYPED row. Both stored codes carry the cause a screen displayed for them, except on an illness row, which displays its own vocabulary. |
| severity | `Optional[common.CodedValue[injuries.InjurySeverity]]` | verified | How bad the injury was, on a HISTORY row; None on every TYPED row. All four stored codes carry the severity a screen displayed for them, except on an illness row, which displays its own vocabulary. |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning, each present only on the kind of row that carries it: `r0` a byte that is 1 on every row of every save, `hi7_date` the time-slot bits of the row's date word, and, on a TYPED row, `r11` and `r12` (unconfirmed). |

## InjuryType

One named injury the game can hand out.

| field | type | status | description |
|---|---|---|---|
| id | `int` | unconfirmed | The code the save stores on an injury of this type (unconfirmed). |
| name | `str` | unconfirmed | The game's own name for the injury, in the language the save was written in (unconfirmed). |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning: a flag byte, and a second id in an id space of its own (unconfirmed). |

## JobVacancy

One job the save's job-centre feed holds.

| field | type | status | description |
|---|---|---|---|
| team_id | `int \| None` | verified | The team the job is at, None where the record names no team. |
| club_uid | `int \| None` | verified | Uid of the club that fields `team_id`, None for a team no club lists and wherever team_id is. |
| club_name | `str \| None` | verified | Denormalised full name of club_uid, None wherever club_uid is. |
| team_slot | `int \| None` | unconfirmed | The team's place in that club's own team list, 0 for its first team; None when the team resolves to no club (unconfirmed). |
| advertised_date | `datetime.date \| None` | verified | Date the vacancy was advertised, None when the stored date does not decode. The time of day the save stores with it is in `unknown["advertised_slot"]`. |
| competition_id | `int \| None` | unconfirmed | Id of the competition the job's team plays in, in the stage id space; None where the record names none (unconfirmed). |
| competition_name | `str \| None` | unconfirmed | Denormalised name of competition_id, None unless the save was opened with a name map that names it (unconfirmed). |
| league_position | `int \| None` | unconfirmed | The team's current position in that competition's table, None where the record stores none, which is about a quarter of rows (unconfirmed). |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning: the role code the vacancy's job title comes from, the advertised date's time-of-day slot, a second date whose meaning is not settled (its raw four bytes as one little-endian int, not a decoded date), an attribute of the competition, and a 0/1 flag (unconfirmed). |

## LeagueTable

One live table: every club the save groups together, with its rows.

| field | type | status | description |
|---|---|---|---|
| competition_id | `int \| None` | unconfirmed | The competition the table was voted to belong to, in the stage id space, which `Suspension.competition_id` also uses; None when the vote could not settle it, which on the corpus is one table in a thousand. Read that beside the shape of the tables: 20% to 28% of them hold one block, and a one-block table meets the vote's half-the-members rule on a majority of one, so it resolves trivially; over the tables of two blocks or more resolution is 0.998 to 1.000. One competition names several tables, because a cup's group stage is one competition holding a table per group. The save stores no link from a table to its competition, so this is a vote on the fixture calendar rather than a stored value (unconfirmed). |
| competition_name | `str \| None` | unconfirmed | Denormalised name of competition_id, which is None unless a name map is supplied, because the save stores no competition names (unconfirmed). |
| club_count | `int` | unconfirmed | How many rows the table holds (unconfirmed). |
| rows | `tuple[league_tables.LeagueTableRow, ...]` | verified | One row per club, in the order the save stores the group. |

## LeagueTableMatch

One match slot of one club's row: a played match, or a slot never played.

| field | type | status | description |
|---|---|---|---|
| slot | `int` | verified | The slot's index in the row, counting from zero. |
| home_or_away | `league_tables.MatchSide \| None` | verified | Which side of the match the row's club was, the home one or the away one, which the save stores as the slot's parity: the even slots are the home ones. That is checked against the fixture calendar's own stored home team on every table whose rows account for exactly one season of it, and it holds on 99.76% to 99.87% of the slots the calendar can settle by itself, against a fifth of a percent were the parity the other way round; the handful that disagree are consistent with rescheduled or neutral-ground meetings. A slot never played carries a side too, since the parity belongs to the slot rather than to what happened in it. It is None only where the build fmsave read the save with has not settled the parity. This is the club's side and not the ground: `Fixture.is_neutral_venue` is the field that says whether a match was played away from the home club's usual ground, and a match at a neutral ground still has a home club and an away club. |
| opponent_team_id | `int \| None` | verified | The opponent's team id exactly as stored, or None for an unplayed slot. |
| opponent_club_uid | `int \| None` | verified | Uid of the club fielding the opponent, or None when the slot is unplayed or no club lists that team. |
| opponent_club_name | `str \| None` | verified | Denormalised name of opponent_club_uid, or None when it does not resolve. |
| opponent_club_short_name | `str \| None` | verified | Denormalised short name of opponent_club_uid, or None when it does not resolve. |
| goals_for | `int \| None` | verified | Goals the club scored, or None for an unplayed slot. |
| goals_against | `int \| None` | verified | Goals the club conceded, or None for an unplayed slot. |
| outcome | `league_tables.MatchOutcome \| None` | verified | Whether the club won, drew or lost, or None for an unplayed slot. |
| points | `int \| None` | verified | Points the club took from the match, or None for an unplayed slot. |

## LeagueTableRow

One club's row in one live table, with its splits and its match slots.

| field | type | status | description |
|---|---|---|---|
| position | `int` | verified | The club's place in the table, counting from one, which is the order the save stores. Read it as the league position and leave the rows alone: a sort by points and goal difference reproduces it on about 92% of tables and disagrees only where the game's own first tie-break, the results between the clubs level on points, decides an order these fields cannot reconstruct. |
| team_id | `int` | verified | The club's first-team id exactly as stored. |
| club_uid | `int \| None` | verified | Uid of the club fielding that team, or None when no club lists it. |
| club_name | `str \| None` | verified | Denormalised name of club_uid, or None when the team does not resolve. |
| club_short_name | `str \| None` | verified | Denormalised short name of club_uid, or None when the team does not resolve. |
| team_slot | `int \| None` | unconfirmed | The team's slot in its club's team list, 0 for the first entry, or None when the team does not resolve (unconfirmed). |
| played | `int` | verified | Matches played in total. On FM27 some cup group stages count matches here that are none of won, drawn or lost. |
| won | `int` | verified | Matches won in total. |
| drawn | `int` | verified | Matches drawn in total. |
| lost | `int` | verified | Matches lost in total. |
| goals_for | `int` | verified | Goals scored in total. |
| goals_against | `int` | verified | Goals conceded in total. |
| points | `int` | verified | Points taken in total, after any adjustment such as a points deduction, so it can differ from the home and away points added together and can be below zero. |
| home | `LeagueTableSplit` |  | The club's home record (every field unconfirmed). |
| away | `LeagueTableSplit` |  | The club's away record (every field unconfirmed). |
| first_half | `LeagueTableSplit` |  | The club's record in the first half of the season (every field unconfirmed). |
| second_half | `LeagueTableSplit` |  | The club's record in the second half of the season (every field unconfirmed). |
| rounds_per_venue | `int \| None` | unconfirmed | How many rounds the group plays at each venue, so the row holds twice this many match slots; None where the save stores the row without match slots, which it does for some tables (unconfirmed). |
| matches | `tuple[league_tables.LeagueTableMatch, ...]` | verified | One entry per match slot, in stored order, including slots never played; empty where the save stores the row without them. |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | The 19 bytes stored in front of the block, one int per byte. The first of them is the row's own place in its table, which is what tells one table from the next and is already reported as `position`; it is kept here so the blob ships whole. The other 18 are undecoded, and they are the only fields in which the save's several copies of a block differ (unconfirmed). |

## LeagueTableSplit

One of a row's four partial records: home, away, first half or second half.

| field | type | status | description |
|---|---|---|---|
| played | `int` | unconfirmed | Matches played in this split (unconfirmed). |
| won | `int` | unconfirmed | Matches won (unconfirmed). |
| drawn | `int` | unconfirmed | Matches drawn (unconfirmed). |
| lost | `int` | unconfirmed | Matches lost (unconfirmed). |
| goals_for | `int` | unconfirmed | Goals scored (unconfirmed). |
| goals_against | `int` | unconfirmed | Goals conceded (unconfirmed). |
| points | `int` | unconfirmed | Points taken (unconfirmed). |

## ManagedClub

A club run by one of the save's human managers.

| field | type | status | description |
|---|---|---|---|
| club_uid | `int` | unconfirmed | Uid of the managed club (unconfirmed). |
| club_name | `str` | unconfirmed | Denormalised full name of club_uid (unconfirmed). |
| club_short_name | `str` | unconfirmed | Denormalised short name of club_uid (unconfirmed). |
| manager_name | `str \| None` | unconfirmed | The human manager's name as the save summary stores it, or None when the summary does not name the manager next to the club (unconfirmed). |
| manager_staff_uid | `int \| None` | unconfirmed | Uid of the human manager's own record, which is a `Staff.uid` and joins to the staff table; None when it cannot be identified exactly. manager_name is this person's name (unconfirmed). |
| balance | `int \| None` | unconfirmed | The club's balance on the save's date, the finances screen's Overall Balance, in the same stored unit as `FinanceMonth`. It is not the last `FinanceMonth.balance`, which closes the previous month: this one also carries the current month's money so far (unconfirmed). None on a build with no layout for it (every FM26 build so far), or when the club has no monthly finance chain or its sponsor prefix does not decode. |
| scouting_budget | `int \| None` | unconfirmed | The club's scouting budget for the season, in the same unit (unconfirmed). It is the season's total, **not** what is left to spend: it stays the same while `scouting_budget_remaining` falls. None on a build with no layout for it (every FM26 build so far), on a save with more than one human manager, or when it cannot be found exactly once. |
| scouting_budget_remaining | `int \| None` | unconfirmed | What is left of scouting_budget (unconfirmed). None whenever scouting_budget is None. |

## MentoringGroup

One mentoring group of one team of the managed club.

| field | type | status | description |
|---|---|---|---|
| team_id | `int` | verified | The team the group belongs to, as the save stores it. |
| club_uid | `int \| None` | verified | Uid of the club that fields `team_id`, None for a team no club lists. |
| club_name | `str \| None` | verified | Denormalised full name of club_uid. |
| team_slot | `int \| None` | unconfirmed | The team's place in that club's own team list, 0 for its first team; None when the team resolves to no club (unconfirmed). |
| group_number | `int` | unconfirmed | The number the save stores with the group, which runs from one up within a team (unconfirmed). |
| label | `str` | verified | The group's label as the save stores it: the game's default wording with its number, or the name the group was given in game. |
| member_uids | `tuple[int \| None, ...]` | verified | Uid of each member, in stored order, None for a member whose stored selector names no player record. |
| member_names | `tuple[str \| None, ...]` | verified | Denormalised name of each entry of `member_uids`, aligned with it and None wherever that uid is. |

## Nation

One row of the save's nation table.

| field | type | status | description |
|---|---|---|---|
| nation_id | `int` | unconfirmed | Save-local nation id, counted from 0. Other tables' nation fields join to this value (unconfirmed). |
| database_id | `int` | unconfirmed | The nation's id in the game's installed database, used to join external name maps (unconfirmed). |

## Official

One match official.

| field | type | status | description |
|---|---|---|---|
| referee_id | `int` | verified | Save-local ID used by `Fixture.referee_id`. |
| person_uid | `int` | verified | The official's person UID. |
| name | `str \| None` | verified | The official's name, or None when no name resolves. |

## Personality

A player's personality profile.

| field | type | status | description |
|---|---|---|---|
| adaptability | `int` | verified | Adaptability. |
| ambition | `int` | verified | Ambition. |
| loyalty | `int` | verified | Loyalty. |
| pressure | `int` | verified | Pressure. |
| professionalism | `int` | verified | Professionalism. |
| sportsmanship | `int` | verified | Sportsmanship. |
| temperament | `int` | verified | Temperament. |
| controversy | `int` | verified | Controversy. |

## Player

A player record from the save's game database.

| field | type | status | description |
|---|---|---|---|
| uid | `int` | unconfirmed | The id fmsave reads for the player's record and joins every table on. It is not the game's Unique ID (that is unique_id): it is the Unique ID of the person stored just before him, so it differs between new games started from the same database (unconfirmed). |
| unique_id | `int \| None` | unconfirmed | The player's Unique ID in the game database, the same in every new game started from that database. The game can give the id of a person it has deleted to one it creates later. None when the save's bytes cannot tell it (unconfirmed). |
| name | `str \| None` | unconfirmed | Display name: common name first, else first plus last name, else legal name (unconfirmed). |
| first_name | `str \| None` | unconfirmed | First name (unconfirmed). |
| last_name | `str \| None` | unconfirmed | Last name (unconfirmed). |
| common_name | `str \| None` | unconfirmed | Common (nickname) name, when the save stores one (unconfirmed). |
| full_name | `str \| None` | unconfirmed | First name plus last name, or None when either is missing (unconfirmed). |
| legal_name | `str \| None` | unconfirmed | The save's stored legal name, or None when the save stores none (unconfirmed). |
| birth_date | `datetime.date \| None` | unconfirmed | Date of birth (unconfirmed). |
| age | `int \| None` | unconfirmed | Age at the save's in-game clock date, or None when birth_date or the clock date is unreadable (unconfirmed). |
| nation_id | `int \| None` | unconfirmed | Save-local id of the player's primary nation (unconfirmed). |
| second_nation_ids | `tuple[int, ...]` | verified | Save-local ids of the player's other eligible nations. |
| home_grown_nation_ids | `tuple[int, ...]` | verified | Save-local ids of nations the player is considered home grown for. |
| home_grown_club_uids | `tuple[int \| None, ...]` | unconfirmed | Uids of clubs the player is considered home grown for, in relation-list order; an entry is None when its club index does not resolve, but still keeps its position. They are Club.uid values and carry its status (unconfirmed). |
| home_grown_club_names | `tuple[str \| None, ...]` | unconfirmed | Denormalised names for home_grown_club_uids, in the same order; None wherever home_grown_club_uids is None (unconfirmed). |
| height_cm | `int` | unconfirmed | Height in centimetres (unconfirmed). |
| ability | `Ability` |  | Current and potential ability. |
| reputation | `Reputation` |  | Reputation figures; never threshold on reputation.bucket. |
| club_uid | `int \| None` | unconfirmed | Uid of the club the player belongs to: the club fielding his registered team, which for a team an affiliate club stores is the club controlling it. None for a free agent or an unresolved team (unconfirmed). |
| club_name | `str \| None` | unconfirmed | Denormalised full name of club_uid (unconfirmed). |
| club_short_name | `str \| None` | unconfirmed | Denormalised short name of club_uid (unconfirmed). |
| club_nation_id | `int \| None` | unconfirmed | Denormalised save-local league nation id of club_uid; None also when that club stores no league nation (unconfirmed). |
| club_fa_nation_id | `int \| None` | unconfirmed | Denormalised save-local FA nation id of club_uid (unconfirmed). |
| club_reputation | `int \| None` | verified | Denormalised reputation of club_uid. |
| club_last_league_position | `int \| None` | verified | Denormalised last completed season league position of club_uid. |
| team_id | `int \| None` | unconfirmed | Id of the player's registered team, or None for a free agent (unconfirmed). |
| team_slot | `int \| None` | unconfirmed | The team's slot in club_uid's team list, which counts that club's own slots first and then the teams it controls at affiliate clubs; None when team_id does not resolve to a club (unconfirmed). |
| team_club_uid | `int \| None` | unconfirmed | Uid of the club whose record stores the player's registered team, when another club controls that team, else None (unconfirmed). |
| team_club_name | `str \| None` | unconfirmed | Denormalised full name of team_club_uid; None wherever team_club_uid is (unconfirmed). |
| club_join_date | `datetime.date \| None` | unconfirmed | Date the player joined his current club; it disagrees with the contract start date for about half of players, so it is not a substitute for it (unconfirmed). |
| natural_positions | `tuple[str, ...]` | verified | Position codes rated at least 18, best first. |
| accomplished_positions | `tuple[str, ...]` | verified | Position codes rated 15 to 17, best first. This is an fmsave classifier label, not text the game itself shows. |
| personality | `players.Personality \| None` |  | Personality profile, or None when no person block validates. |
| attributes | `Attributes` |  | The 52 non-foot attributes, on the 1 to 20 display scale. |
| raw_attributes | `Attributes` |  | The same 52 attributes, on the 1 to 100 raw scale. |
| left_foot | `int` | verified | Left foot strength, on the 1 to 20 display scale. |
| right_foot | `int` | verified | Right foot strength, on the 1 to 20 display scale. |
| raw_left_foot | `int` | verified | Left foot strength, on the 1 to 100 raw scale. |
| raw_right_foot | `int` | verified | Right foot strength, on the 1 to 100 raw scale. |
| positions | `Positions` |  | The 15 position ratings. |
| transfer_value | `int \| None` | verified | Transfer value in the save's base currency, set only when transfer_value_state is OK. |
| transfer_value_state | `<enum 'TransferValueState'>` | unconfirmed | How transfer_value was read from the save (unconfirmed). |
| raw_condition | `int` | verified | Condition, on the 0 to 10000 scale the save stores it on. The game shows condition as a percentage, which is this divided by 100. |
| raw_match_sharpness | `int` | verified | Match sharpness, on the 0 to 10000 scale the save stores it on. The game shows it as a percentage, which is this divided by 100. |
| traits | `tuple[common.CodedValue[players.Trait], ...]` | verified | Named player traits; an unnamed bit is Trait.UNKNOWN with raw set to the bit number. |
| trait_bits | `int \| None` | verified | The raw trait bitmask, or None when no person block validates. |
| on_loan | `bool \| None` | verified | Whether the player is on loan from the club of his contract in effect: True when he is registered with another club's team and the save holds a loan for him there that has not ended, False when it does not, and None when his club or his contract in effect is unknown. A player registered with a team his own club controls, such as a B team, is a player of that club, not on loan. |
| loan_parent_club_uid | `int \| None` | unconfirmed | Uid of the club of the contract in effect when on_loan is True, else None. It is the contract's club_uid under another name, so it carries the same status (unconfirmed). |
| loan_parent_club_name | `str \| None` | unconfirmed | Denormalised name of loan_parent_club_uid (unconfirmed). |
| loan_start | `datetime.date \| None` | verified | Date the loan began when on_loan is True, else None. It is also None when the loan's stored start does not decode as a game date, which keeps an unreadable start from costing the player his loan; no save read so far holds such a loan. |
| loan_end | `datetime.date \| None` | verified | Date the loan ends when on_loan is True, else None. |
| contract | `contracts.Contract \| None` |  | The player's current contract, or None when a current contract cannot be established. |
| suspensions | `tuple[suspensions.PlayerSuspension, ...] \| None` | verified | The player's unserved suspensions, in the order the save stores them, including bans the game no longer displays; () when the player has none. None when the FM27 reader cannot establish suspension coverage. |

## PlayerMatchStats

One player's record of one match the save still holds.

| field | type | status | description |
|---|---|---|---|
| player_uid | `int` | unconfirmed | Uid of the player the record belongs to, which is the player whose object holds it (unconfirmed). |
| player_name | `str \| None` | unconfirmed | Denormalised name of player_uid (unconfirmed). |
| date | `date` | verified | The date the match was played. |
| competition_id | `int` | verified | Id of the competition, in the **stage** id space. It is stored on the record itself rather than reached through a stage. |
| opponent_team_id | `int` | verified | The opposing team's id, exactly as stored. It is a team id and never a club index, and a reserve or youth side has its own. |
| opponent_club_uid | `int \| None` | verified | Uid of the club fielding the opposing team, or None when no club lists that team. |
| opponent_club_name | `str \| None` | verified | Denormalised name of opponent_club_uid, or None when the team does not resolve. |
| opponent_club_short_name | `str \| None` | verified | Denormalised short name of opponent_club_uid, or None when the team does not resolve. |
| opponent_team_slot | `int \| None` | unconfirmed | The opposing team's slot in its club's team list, 0 for the first entry, or None when the team does not resolve (unconfirmed). |
| has_stats | `bool` | unconfirmed | Whether the record holds statistics for the match. A record without them keeps the date, the competition and the opponent and nothing else, so every field below that can be None is None when this is false. On the saves measured, such a record is a match of his team that he did not play in (unconfirmed). |
| position | `Optional[common.CodedValue[matches.MatchPosition]]` | verified | The position played, as a coded value over the mask the record stores. Only the goalkeeper bit is named; every other mask keeps its raw value and reads as UNKNOWN. None when the save holds no statistics for the match. |
| minutes | `int \| None` | unconfirmed | Minutes played, or None when the save holds no statistics for the match. No value the game displays has been matched to this number; what says it is minutes played is its shape. On the saves measured about half the matches with statistics hold exactly 90, over 0.993 hold 90 or less, none holds more than 130, and the rest are spread over the values below 90 rather than clustered (unconfirmed). |
| left_at_minute | `int \| None` | unconfirmed | The minute the player left the pitch, whether he was substituted or sent off. None when he was on it at the final whistle, which the save stores as a zero, and None as well when the save holds no statistics for the match; `has_stats` tells those two apart. It is never 0, so a filter such as `left_at_minute < 10` selects the early departures and nobody else (unconfirmed). |
| goals | `int \| None` | verified | Goals scored, or None when the save holds no statistics for the match. |
| assists | `int \| None` | unconfirmed | Assists, or None when the save holds no statistics for the match. This is a **hypothesis**: no displayed label has been matched to this byte, and the count shown on a player's season statistics screen is what would confirm it (unconfirmed). |
| rating | `float \| None` | unconfirmed | The match rating, which is the stored number divided by ten and so exact to one decimal. None when the save holds no statistics for the match, and None as well when the game rated nobody in it, which the save stores as a zero; `has_stats` tells those two apart, and the stored zero is kept as `unknown["rating_raw"]` so nothing is dropped. A rating is never 0.0, so an average over this column is an average of the ratings the game actually gave (unconfirmed). |
| passes_attempted | `int \| None` | unconfirmed | Passes attempted, or None when the save holds no statistics for the match (unconfirmed). |
| passes_completed | `int \| None` | unconfirmed | Passes completed, or None when the save holds no statistics for the match (unconfirmed). |
| stats_in_range | `bool` | unconfirmed | fmsave's own sanity flag, not a value the save stores: true when the save holds this match's statistics and its minutes, rating and goals are all inside the bounds a match can reach. A false flag never blanks a value; every number is kept exactly as stored so a caller can see what the save holds (unconfirmed). |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning. "role_code" moves with the position played but its meaning is not established, and it is absent from the mapping for a match the save holds no statistics for; "tag" is stored beside the date and is always read; "rating_raw" is the stored rating, kept only where it is zero, which is the one value `rating` itself cannot carry (unconfirmed). |

## PlayerSeasonHistory

One archived statistics line for a player and team.

| field | type | status | description |
|---|---|---|---|
| player_uid | `int` | verified |  |
| player_name | `str \| None` | verified |  |
| kind | `<enum 'SeasonStatsKind'>` | verified |  |
| team_id | `int \| None` | verified | Archived team reference, or None for the missing-reference sentinel. |
| club_uid | `int \| None` | verified |  |
| club_name | `str \| None` | verified |  |
| club_short_name | `str \| None` | verified |  |
| team_slot | `int \| None` | unconfirmed |  |
| starts | `int` | verified |  |
| substitute_appearances | `int` | verified |  |
| minutes | `int` | verified |  |
| rated_appearances | `int` | verified |  |
| average_rating | `float \| None` | verified |  |
| player_of_the_match | `int` | unconfirmed |  |
| goals | `int` | verified |  |
| assists | `int` | verified |  |
| expected_goals | `float` | verified |  |
| non_penalty_expected_goals | `float` | unconfirmed |  |
| expected_assists | `float` | verified |  |
| shots | `int` | verified |  |
| shots_on_target | `int` | verified |  |
| shots_outside_box | `int` | verified |  |
| goals_outside_box | `int \| None` | unconfirmed |  |
| free_kick_shots | `int` | unconfirmed |  |
| penalties_taken | `int` | unconfirmed |  |
| penalties_scored | `int` | unconfirmed |  |
| passes_attempted | `int` | verified |  |
| passes_completed | `int` | verified |  |
| progressive_passes | `int` | verified |  |
| key_passes | `int` | verified |  |
| open_play_key_passes | `int` | verified |  |
| clear_cut_chances_created | `int` | verified |  |
| crosses_attempted | `int` | verified |  |
| crosses_completed | `int` | verified |  |
| open_play_crosses_attempted | `int` | unconfirmed |  |
| open_play_crosses_completed | `int \| None` | unconfirmed |  |
| dribbles | `int` | verified |  |
| offsides | `int` | verified |  |
| distance_km | `float` | verified |  |
| high_intensity_sprints | `int` | verified |  |
| aerial_challenges_attempted | `int \| None` | verified |  |
| headers_won | `int \| None` | verified |  |
| key_headers | `int` | unconfirmed |  |
| tackles_attempted | `int` | verified |  |
| tackles_completed | `int` | verified |  |
| key_tackles | `int` | unconfirmed |  |
| interceptions | `int` | verified |  |
| possession_won | `int` | verified |  |
| possession_lost | `int` | unconfirmed |  |
| pressures_attempted | `int \| None` | verified |  |
| pressures_completed | `int \| None` | verified |  |
| blocks | `int \| None` | unconfirmed |  |
| shots_blocked | `int` | unconfirmed |  |
| clearances | `int \| None` | verified |  |
| fouls_made | `int` | verified |  |
| fouls_against | `int` | verified |  |
| yellow_cards | `int` | verified |  |
| red_cards | `int` | unconfirmed |  |
| mistakes_leading_to_goal | `int` | unconfirmed |  |
| clean_sheets | `int` | unconfirmed |  |
| goals_allowed | `int` | unconfirmed |  |
| saves_held | `int \| None` | unconfirmed |  |
| saves_parried | `int \| None` | unconfirmed |  |
| saves_tipped | `int \| None` | unconfirmed |  |
| shots_on_target_faced | `int \| None` | unconfirmed |  |
| expected_goals_prevented | `float` | unconfirmed |  |
| season_year | `int` | unconfirmed | Candidate season year; whether it identifies the start or end of a season is unknown (unconfirmed). |
| competition_reference | `int` | unconfirmed | Raw candidate competition reference, without a confirmed mapping to competition entities or database ids (unconfirmed). |

## PlayerSeasonStats

One player's stats for one competition type and one team this season.

| field | type | status | description |
|---|---|---|---|
| player_uid | `int` | verified | Uid of the player. |
| player_name | `str \| None` | verified | Denormalised name of player_uid. |
| kind | `<enum 'SeasonStatsKind'>` | verified | The competition type the row covers. |
| team_id | `int \| None` | verified | The team the row is for: the player's current team, or another team they played for this season. |
| club_uid | `int \| None` | verified | Uid of the club whose team list holds team_id, or None when no club lists it. |
| club_name | `str \| None` | verified | Denormalised name of club_uid, or None when the team does not resolve. |
| club_short_name | `str \| None` | verified | Denormalised short name of club_uid, or None when the team does not resolve. |
| team_slot | `int \| None` | unconfirmed | The team's slot in its club's team list, 0 for the first entry, or None when the team does not resolve (unconfirmed). |
| starts | `int` | verified | Appearances from the start. |
| substitute_appearances | `int` | verified | Appearances from the bench. |
| minutes | `int` | verified | Minutes played. |
| rated_appearances | `int` | verified | Appearances the game gave a rating. |
| average_rating | `float \| None` | verified | Average match rating, or None when no appearance was rated. |
| player_of_the_match | `int` | unconfirmed | Player of the match awards (unconfirmed). |
| goals | `int` | verified | Goals. |
| assists | `int` | verified | Assists. |
| expected_goals | `float` | verified | Expected goals (xG). |
| non_penalty_expected_goals | `float` | unconfirmed | Expected goals from shots other than penalties (npxG) (unconfirmed). |
| expected_assists | `float` | verified | Expected assists (xA). |
| shots | `int` | verified | Shots. |
| shots_on_target | `int` | verified | Shots on target. |
| shots_outside_box | `int` | verified | Shots from outside the box. |
| goals_outside_box | `int \| None` | unconfirmed | Goals from outside the box. Always None for now: the stored count runs above goals and shots on target on some rows, so it is withheld until its meaning is known (unconfirmed). |
| free_kick_shots | `int` | unconfirmed | Shots from free kicks (unconfirmed). |
| penalties_taken | `int` | unconfirmed | Penalties taken (unconfirmed). |
| penalties_scored | `int` | unconfirmed | Penalties scored (unconfirmed). |
| passes_attempted | `int` | verified | Passes attempted. |
| passes_completed | `int` | verified | Passes completed. |
| progressive_passes | `int` | verified | Progressive passes. |
| key_passes | `int` | verified | Key passes. |
| open_play_key_passes | `int` | verified | Key passes in open play. |
| clear_cut_chances_created | `int` | verified | Clear-cut chances created. The game's "chances created" figure counts the same thing. |
| crosses_attempted | `int` | verified | Crosses attempted. |
| crosses_completed | `int` | verified | Crosses completed. |
| open_play_crosses_attempted | `int` | unconfirmed | Crosses attempted in open play (unconfirmed). |
| open_play_crosses_completed | `int \| None` | unconfirmed | Crosses completed in open play; None on a goalkeeper's line (unconfirmed). |
| dribbles | `int` | verified | Dribbles made. |
| offsides | `int` | verified | Offsides. |
| distance_km | `float` | verified | Distance covered, in kilometres. |
| high_intensity_sprints | `int` | verified | High intensity sprints. |
| aerial_challenges_attempted | `int \| None` | verified | Aerial challenges attempted; None for a goalkeeper. |
| headers_won | `int \| None` | verified | Headers won; None for a goalkeeper. |
| key_headers | `int` | unconfirmed | Key headers (unconfirmed). |
| tackles_attempted | `int` | verified | Tackles attempted. |
| tackles_completed | `int` | verified | Tackles completed. |
| key_tackles | `int` | unconfirmed | Key tackles (unconfirmed). |
| interceptions | `int` | verified | Interceptions. |
| possession_won | `int` | verified | Times the player won possession. |
| possession_lost | `int` | unconfirmed | Times the player lost possession (unconfirmed). |
| pressures_attempted | `int \| None` | verified | Pressures attempted, or None when unsupported. |
| pressures_completed | `int \| None` | verified | Pressures completed, or None when unsupported. |
| blocks | `int \| None` | unconfirmed | Blocks; None for a goalkeeper (unconfirmed). |
| shots_blocked | `int` | unconfirmed | Shots blocked while defending (unconfirmed). |
| clearances | `int \| None` | verified | Clearances; None for a goalkeeper. |
| fouls_made | `int` | verified | Fouls made. |
| fouls_against | `int` | verified | Fouls suffered. |
| yellow_cards | `int` | verified | Yellow cards. |
| red_cards | `int` | unconfirmed | Red cards (unconfirmed). |
| mistakes_leading_to_goal | `int` | unconfirmed | Mistakes leading to a goal (unconfirmed). |
| clean_sheets | `int` | unconfirmed | Clean sheets; usually 0 for an outfield player (unconfirmed). |
| goals_allowed | `int` | unconfirmed | Goals conceded as goalkeeper; usually 0 for an outfield player (unconfirmed). |
| saves_held | `int \| None` | unconfirmed | Saves held; None for an outfield player (unconfirmed). |
| saves_parried | `int \| None` | unconfirmed | Saves parried; None for an outfield player (unconfirmed). |
| saves_tipped | `int \| None` | unconfirmed | Saves tipped; None for an outfield player (unconfirmed). |
| shots_on_target_faced | `int \| None` | unconfirmed | Shots on target faced as goalkeeper; None for an outfield player (unconfirmed). |
| expected_goals_prevented | `float` | unconfirmed | Expected goals prevented (xGP); negative when a goalkeeper conceded more than expected (unconfirmed). |

## PlayerSuspension

One unserved suspension, as listed on its player.

| field | type | status | description |
|---|---|---|---|
| scope | `<enum 'SuspensionScope'>` | verified | What the ban covers: one competition, a whole nation, or UNKNOWN for a scope code never measured. |
| scope_code | `int` | verified | The scope code exactly as the save stores it: 1 for a competition-wide ban, 5, 6 or 10 for a nation-wide one. What separates 5, 6 and 10 is not known. |
| competition_id | `int \| None` | verified | Id of the competition the ban applies to, in the **stage** id space, so it joins `stages()`, `competitions()`, `fixtures()`, `league_tables()` and `player_match_stats()`. None unless the scope is COMPETITION. |
| competition_name | `str \| None` | unconfirmed | Denormalised name of competition_id, which is None unless a name map is supplied, because the save stores no competition names. A competition the game itself created during the career has a database id no name source outside the save carries, so some rows stay unnamed even with a full map (unconfirmed). |
| nation_id | `int \| None` | verified | Save-local id of the nation whose competitions the ban covers, in the same id space as `Club.nation_id` and `Player.nation_id`. None unless the scope is NATION. |
| issued_date | `date` | verified | Date the ban was issued. |

## Positions

The 15 position ratings, in the player rating array order.

| field | type | status | description |
|---|---|---|---|
| gk | `int` | verified | Goalkeeper. |
| sw | `int` | verified | Sweeper. |
| dl | `int` | verified | Left back. |
| dc | `int` | verified | Centre back. |
| dr | `int` | verified | Right back. |
| dm | `int` | verified | Defensive midfielder. |
| ml | `int` | verified | Left midfielder. |
| mc | `int` | verified | Central midfielder. |
| mr | `int` | verified | Right midfielder. |
| aml | `int` | verified | Attacking midfielder, left. |
| amc | `int` | verified | Attacking midfielder, centre. |
| amr | `int` | verified | Attacking midfielder, right. |
| stc | `int` | verified | Striker. |
| wbl | `int` | verified | Left wing back. |
| wbr | `int` | verified | Right wing back. |

## ReaderCheck

One reader's evaluated checks, its record count and its anomaly counts.

| field | type | status | description |
|---|---|---|---|
| reader | `str` |  | The reader the checks belong to, named as `ReaderValidation.reader` names it. |
| record_count | `int` |  | How many records the reader decoded. |
| gates | `tuple[fmsave._checks.GateResult, ...]` |  | The reader's checks, in a fixed order; empty when it has none of its own. |
| anomalies | `collections.abc.Mapping[str, int]` |  | Counts of records the reader decoded but flags, such as unresolved teams. |

## ReaderValidation

How one reader fared in `validate_save`.

| field | type | status | description |
|---|---|---|---|
| reader | `str` |  | The reader: "clubs", "players", "contracts", "suspensions", "managed_clubs", "stages", "competitions", "fixtures", "league_tables", "transfer_windows", "competition_rules", "player_match_stats", "player_season_stats", "player_season_history", "stadiums", "finances", "sponsorships", "affiliates", "job_vacancies", "staff", "staff_lists", "injury_types", "injuries", "training", "mentoring", "tactics", "set_pieces", "selections" or "facilities". |
| status | `ReaderStatus` |  | "ok" when the reader returned its table without failing a blocking check, "failed" for a blocking failure, and "error" when it raised another fmsave error. |
| record_count | `int \| None` |  | How many records the reader decoded, or None when it did not get far enough to count them. |
| gates | `tuple[fmsave._checks.GateResult, ...]` |  | The reader's checks, in a fixed order; empty when the reader has no checks of its own, as the managed-club reader does not, or when it did not get far enough. |
| coverage | `collections.abc.Mapping[str, float]` |  | The table's coverage (the share of non-None values per column); empty unless the status is "ok". |
| anomalies | `collections.abc.Mapping[str, int]` |  | Counts of records the reader decoded but flags, such as unresolved teams. |

## Reputation

A player's reputation figures.

| field | type | status | description |
|---|---|---|---|
| bucket | `int` | unconfirmed | Coarse reputation bucket that loses precision (unconfirmed). |
| home | `int` | verified | Home reputation. |
| current | `int` | verified | Current reputation. |
| world | `int` | verified | World reputation. |

## RulesRound

One round of a competition's calendar, as the rules block stores it.

| field | type | status | description |
|---|---|---|---|
| number | `int` | unconfirmed | The round's number, counting from one. A round the save does not number stores a value that reads here as 256 rather than as a guess (unconfirmed). |
| date | `datetime.date \| None` | unconfirmed | The date the round is played on, or None when the stored date does not decode (unconfirmed). |
| match_count | `int` | unconfirmed | Unidentified u32 retained unchanged under its legacy field name. It is not a dependable fixture count: the same dated row can change from 2 to 10 as a career advances, and larger values such as 256 and 8192 occur in complete calendars. No bit masks or flag meanings are inferred (unconfirmed). |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning. "kind" and "b5" are the two unidentified bytes the round record carries (unconfirmed). |

## SaveInfo

Facts about a save, read when it is opened.

| field | type | status | description |
|---|---|---|---|
| game | `str` | verified | Game edition, for example "FM26". |
| build | `str` | verified | Version and build that last wrote the save, for example "26.3.2+2329565". |
| build_number | `int` | verified | The numeric build. |
| known_build | `bool` | verified | Whether fmsave has a layout registered for every reader for this build. It describes layout coverage. Use `fmsave validate` to check field statuses. It is False for an FM27 build that borrows another build's layouts. |
| db_version | `str` | unconfirmed | Game database version string stored in the save (unconfirmed). |
| game_date | `datetime.date \| None` | unconfirmed | In-game date, falling back to the structured save summary before the first Continue when the normal clock is null; None when neither is readable (unconfirmed). |
| time_slot | `int` | unconfirmed | Intra-day time slot stored with the in-game date (unconfirmed). |
| save_name | `str` | verified | The save's own name. `fmsave info` hides it unless --show-name is passed. |
| sections | `tuple[meta.SectionInfo, ...]` | verified | Every named section in file order. |
| summary_strings | `tuple[str, ...]` | unconfirmed | The readable strings stored in the save summary, in file order, including the build string. They can hold the human manager's name and club and competition names, so `fmsave info` does not show them (unconfirmed). |
| section_schemas | `collections.abc.Mapping[str, int]` | verified | Schema number of every named section, read-only. |
| file_name | `str` | verified | The save's file name, without its folder. |

## SectionInfo

One named section from the save's own directory.

| field | type | status | description |
|---|---|---|---|
| name | `str` | verified | Section name. |
| extension | `str` | verified | ".dat" or ".cmt". |
| file_offset | `int` | verified | Where the section's compressed frame starts in the file. |
| compressed_size | `int` | verified | Size of the compressed frame in bytes. |
| decompressed_size | `int` | verified | Size of the section once decompressed. |
| schema | `int` | verified | Schema number stored at the start of the section. |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Directory values without an identified meaning ("tail0", "tail1") (unconfirmed). |

## Selection

One player picked in one team's stored selection: a starter or a substitute.

| field | type | status | description |
|---|---|---|---|
| club_uid | `int \| None` | unconfirmed | Uid of the club the team plays for, None for a team no club lists (unconfirmed). |
| club_name | `str \| None` | unconfirmed | Denormalised full name of club_uid (unconfirmed). |
| team_id | `int` | unconfirmed | The team the selection belongs to, as the save stores it (unconfirmed). |
| team_slot | `int \| None` | unconfirmed | The team's place in that club's own team list, 0 for its first team; None when the team resolves to no club (unconfirmed). |
| substitute | `bool` | unconfirmed | False for a starter, True for a substitute (unconfirmed). |
| slot | `int` | unconfirmed | The place within the starters or within the substitutes, counting from zero in stored order; a starter's is the tactic slot it fills, and a substitute's 0 is the first substitute the game lists (unconfirmed). |
| player_uid | `int \| None` | unconfirmed | Uid of the picked player, None when the stored pick names no player record (unconfirmed). |
| player_name | `str \| None` | unconfirmed | Denormalised name of player_uid (unconfirmed). |

## SetPieceRoutine

One set-piece routine slot of one team, named or unnamed.

| field | type | status | description |
|---|---|---|---|
| club_uid | `int \| None` | unconfirmed | Uid of the club the team plays for, None for a team no club lists (unconfirmed). |
| club_name | `str \| None` | unconfirmed | Denormalised full name of club_uid (unconfirmed). |
| team_id | `int` | unconfirmed | The team the slot belongs to, as the save stores it (unconfirmed). |
| team_slot | `int \| None` | unconfirmed | The team's place in that club's own team list, 0 for its first team; None when the team resolves to no club (unconfirmed). |
| slot | `int` | unconfirmed | The routine's place in the team's stored routines, counting from zero in stored order. Which set-piece situation a slot is for is not stored as text, so the slot number is all there is to go on (unconfirmed). |
| name | `str \| None` | verified | Stored routine name, or None when unnamed. A team may store more than 20 routines. |

## Sponsorship

One sponsorship contract of one club, running or ended.

| field | type | status | description |
|---|---|---|---|
| club_uid | `int` | unconfirmed | Uid of the club (unconfirmed). |
| club_name | `str` | unconfirmed | Denormalised full name of club_uid (unconfirmed). |
| kind | `common.CodedValue[finances.SponsorType]` | unconfirmed | What kind of sponsorship it is. Only the codes an FM27 screen named carry a label; every other code, and every FM26 code, is UNKNOWN (unconfirmed). |
| start | `datetime.date \| None` | verified | The day the contract starts. |
| end | `datetime.date \| None` | verified | The day it ends. |
| total_value | `int` | verified | The contract's whole value. On most running contracts it is the annual value times the contract's whole years. The screen's Duration column is `total_value / annual_value` in years, which can differ from the span between `start` and `end`, so do not work a duration out from the dates. |
| annual_value | `int` | verified | What a running contract pays a year. A contract that has ended can still carry a non-zero annual value, often equal to its total value, so neither a zero nor a non-zero value says whether the contract is still running; compare `end` with the save's date for that. A running contract is not always counted in the screen's sponsorship income either: on one FM27 club an unexpired kind 6 row was left out of it. |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning (unconfirmed). |

## SquadPlannerSlot

One numbered slot in the human manager's squad planner.

| field | type | status | description |
|---|---|---|---|
| season_offset | `int` | unconfirmed | 0 for the current season, 1 for the next, and 2 for the season after (unconfirmed). |
| slot | `int` | unconfirmed | Slot number from 1 to 27 in stored order (unconfirmed). |
| player_uids | `tuple[int \| None, ...]` | unconfirmed | Player UIDs in depth order (unconfirmed). An empty slot is an empty tuple. Each unresolved player reference appears as None in its original place. |

## Stadium

One ground the save's database holds.

| field | type | status | description |
|---|---|---|---|
| uid | `int` | unconfirmed | The ground's uid, which is the stored value plus one, the same convention club uids follow. A stadium uid that equals a club uid is a coincidence: the two are separate id spaces and must never be joined on (unconfirmed). |
| name | `str \| None` | unconfirmed | The ground's name as the save stores it inline, or None when the save stores none, which is the case for nearly every ground: the game takes the name from its installed database instead (unconfirmed). |
| total_capacity | `int` | verified | The ground's total capacity, seated and standing together: the first figure the game's facilities screen shows. The seated part is `seated_capacity`; the two are equal on a ground the screen calls all-seater. |
| seated_capacity | `int` | unconfirmed | How many of the total are seats: the figure the facilities screen shows in brackets as seated, and the same as the total on an all-seater ground. It is at or below the total on all but one ground across the saves measured, and it is zero on roughly two grounds in five; on the one FM27 ground compared, the screen then shows a single plain figure with no seated part (unconfirmed). |
| expansion_capacity | `int` | verified | The capacity the ground would hold expanded, which is at or above the total capacity on all but a handful of grounds. |
| capacity | `int \| None` | unconfirmed | The capacity used in normal matches, the lower figure the FM27 facilities screen shows after the total on the one all-seater ground compared. It is empty where the save stores zero, which is about four grounds in five, and at or below the total on all but a handful of grounds (unconfirmed). |
| owner_club_uid | `int \| None` | unconfirmed | Uid of the club that owns the ground, or None when the save names no owner or names a club it does not list. A ground with no stored owner is the council's: the game's own facilities screen shows one such ground as owned by the council, so an empty owner is an answer rather than a gap. Owning a ground is not the same as playing at it (unconfirmed). |
| owner_club_name | `str \| None` | unconfirmed | Denormalised name of owner_club_uid, or None when there is no owner or the owner does not resolve (unconfirmed). |
| home_club_uids | `tuple[int, ...] \| None` | unconfirmed | Uids of the clubs whose home ground this is, in ascending order. It comes from the fixture calendar, not from any stored link: a club has a home ground once the calendar records enough first-team home matches for it, and that ground is the one it used most. It is empty for a ground no club uses often enough, and a ground several clubs share lists each of them. None means the fixture calendar is unavailable, not that no club uses the ground (unconfirmed). |
| home_club_names | `tuple[str, ...] \| None` | unconfirmed | Denormalised names of home_club_uids, in the same order; None when the fixture calendar is unavailable (unconfirmed). |
| pitch_length_dm | `int` | verified | The pitch's length in decimetres. The facilities screen shows whole metres and drops the rest, so a stored 1005 shows as 100 m. A few grounds store a length past `pitch_max_length_dm`, and the screen shows the maximum for such a ground; the value is returned as stored. |
| pitch_width_dm | `int` | verified | The pitch's width in decimetres. As with the length, a few grounds store a width past `pitch_max_width_dm`, and it is returned as stored. |
| pitch_min_length_dm | `int` | unconfirmed | The shortest pitch length the ground allows (unconfirmed). |
| pitch_min_width_dm | `int` | unconfirmed | The narrowest pitch width the ground allows (unconfirmed). |
| pitch_max_length_dm | `int` | verified | The longest pitch length the ground allows. |
| pitch_max_width_dm | `int` | verified | The widest pitch width the ground allows. |
| built_date | `datetime.date \| None` | verified | The date the ground was built, or None when the save stores none. Grounds built in the 1800s keep their year, as the game's facilities screen shows it; a year before 1800 reads as None. A few grounds carry a date after the save's own clock. |
| rebuilt_date | `datetime.date \| None` | verified | The date the ground was last rebuilt, or None when the save stores none. |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning: two capacity-like words, a small code, a third date as one little-endian int, and the whole flags byte whose 0x10 bit is what says the row carries its name inline. "u17" is the first capacity-like word, which `seated_capacity` now carries; it stays here, with the same value, so code that reads it keeps working (unconfirmed). |

## Staff

One member of staff at one club.

| field | type | status | description |
|---|---|---|---|
| uid | `int` | unconfirmed | The id fmsave reads for the person's object and joins every table on. It is not the game's Unique ID (that is unique_id): it is the Unique ID of the person stored just before him, so it differs between new games started from the same database (unconfirmed). |
| unique_id | `int \| None` | unconfirmed | The person's Unique ID in the game database, the same in every new game started from that database. The game can give the id of a person it has deleted to one it creates later. None when the save's bytes cannot tell it (unconfirmed). |
| is_human_manager | `bool` | unconfirmed | Whether this is the save's own human manager (unconfirmed). |
| name | `str \| None` | unconfirmed | Common name, else first and last name, else legal name (unconfirmed). |
| first_name | `str \| None` | unconfirmed | First name (unconfirmed). |
| last_name | `str \| None` | unconfirmed | Surname (unconfirmed). |
| common_name | `str \| None` | unconfirmed | The name the game shows in place of the full name (unconfirmed). |
| full_name | `str \| None` | unconfirmed | First and last name together, when both are known (unconfirmed). |
| legal_name | `str \| None` | unconfirmed | The stored legal name (unconfirmed). |
| birth_date | `datetime.date \| None` | unconfirmed | Date of birth (unconfirmed). |
| age | `int \| None` | unconfirmed | Age at the save's in-game date (unconfirmed). |
| nation_id | `int \| None` | unconfirmed | Save-local nation id (unconfirmed). |
| club_uid | `int` | verified | Uid of the club the person works for. |
| club_name | `str` | verified | Denormalised full name of club_uid. |
| team_id | `int \| None` | verified | The team his contract registers him with, or on FM27 the team of a role he holds with no contract; None when neither is read. |
| team_slot | `int \| None` | unconfirmed | That team's slot in the club's team list, None wherever team_id is (unconfirmed). |
| job | `Optional[common.CodedValue[staff.StaffJob]]` | unconfirmed | His job at the club, None where no record of it is read, which is every row on FM26 (unconfirmed). |
| listed_club_uid | `int \| None` | unconfirmed | The club whose own staff list holds him, which is club_uid unless an affiliate side lists him; None when no list holds him (unconfirmed). |
| listed_club_name | `str \| None` | unconfirmed | Denormalised full name of listed_club_uid; None wherever listed_club_uid is (unconfirmed). |
| in_club_lists | `bool` | unconfirmed | Whether a club's staff list holds him at all (unconfirmed). |
| list_indexes | `tuple[int, ...]` | unconfirmed | Which of the three lists hold him, 0 to 2, empty when none does (unconfirmed). |
| has_contract | `bool` | unconfirmed | Whether a contract at club_uid was read for him (unconfirmed). |
| wage | `int \| None` | verified | What the contract pays, per week, in the save's base currency; None without a contract. |
| contract_start | `datetime.date \| None` | verified | The day the contract started. |
| contract_end | `datetime.date \| None` | unconfirmed | The day it ends, None when the save stores none (unconfirmed). |
| ability | `players.Ability \| None` |  | Current and potential ability, None when the object carries no readable ability block, as the human manager's does not. |
| personality | `players.Personality \| None` |  | The eight personality values, None without a name block. |
| attributes | `staff.StaffAttributes \| None` |  | Adaptability and any readable staff ratings, None without a name block. |
| preferences | `staff.StaffPreferences \| None` |  | The named preferences, None when the object carries no readable ability block. |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning (unconfirmed). The ability-block keys (`entry_count`, `r4` to `r12` and every `preference_slot_*`) are absent when that block does not read, and the `contract_*` keys when no contract was read. |

## StaffAttributes

Ratings stored for a staff member.

| field | type | status | description |
|---|---|---|---|
| adaptability | `int` | verified | Adaptability. |
| goalkeeping | `int \| None` | unconfirmed | Goalkeeping (unconfirmed). |
| judging_player_ability | `int \| None` | unconfirmed | Judging player ability (unconfirmed). |
| judging_player_potential | `int \| None` | unconfirmed | Judging player potential (unconfirmed). |
| people_management | `int \| None` | unconfirmed | People management (unconfirmed). |
| motivating | `int \| None` | unconfirmed | Motivating (unconfirmed). |
| physiotherapy | `int \| None` | unconfirmed | Physiotherapy (unconfirmed). |
| tactical_knowledge | `int \| None` | unconfirmed | Tactical knowledge (unconfirmed). |
| attacking | `int \| None` | unconfirmed | Attacking (unconfirmed). |
| defending | `int \| None` | unconfirmed | Defending (unconfirmed). |
| fitness | `int \| None` | unconfirmed | Fitness (unconfirmed). |
| possession | `int \| None` | unconfirmed | Possession (unconfirmed). |
| technical | `int \| None` | unconfirmed | Technical (unconfirmed). |
| tactical | `int \| None` | unconfirmed | Tactical (unconfirmed). |
| analysing_data | `int \| None` | unconfirmed | Analysing data (unconfirmed). |
| sports_science | `int \| None` | unconfirmed | Sports science (unconfirmed). |
| negotiating | `int \| None` | unconfirmed | Negotiating (unconfirmed). |
| judging_staff_ability | `int \| None` | unconfirmed | Judging staff ability (unconfirmed). |
| set_pieces | `int \| None` | unconfirmed | Set pieces (unconfirmed). |
| authority | `int \| None` | unconfirmed | Authority (unconfirmed). |
| working_with_youngsters | `int \| None` | unconfirmed | Working with youngsters (unconfirmed). |
| determination | `int \| None` | unconfirmed | Determination (unconfirmed). |

## StaffList

One of the three staff lists a club record holds, for one club.

| field | type | status | description |
|---|---|---|---|
| club_uid | `int` | unconfirmed | Uid of the club whose record holds the list (unconfirmed). |
| club_name | `str` | unconfirmed | Denormalised full name of club_uid (unconfirmed). |
| list_index | `int` | unconfirmed | Which of the club's three lists this is, 0 to 2 (unconfirmed). |
| staff_uids | `tuple[int, ...]` | unconfirmed | The uid of each person the list holds, in stored order. They are `Staff.uid` values and join to the staff table (unconfirmed). |
| staff_names | `tuple[str \| None, ...]` | unconfirmed | Each of those people's name, aligned with staff_uids (unconfirmed). |

## StaffPreferences

How a member of staff prefers a team to be run, each on a 1 to 20 scale.

| field | type | status | description |
|---|---|---|---|
| attacking | `int` | verified | How attacking a side he wants. |
| business | `int` | verified | How commercial he wants the club to be. |
| directness | `int` | verified | How direct he wants the passing. |
| interference | `int` | verified | How much he involves himself in other people's work. |
| patience | `int` | verified | How patient he is with a plan. |
| trigger_press | `int` | verified | How eagerly he wants the side to press. |
| resources | `int` | verified | How freely he wants the club's resources spent. |
| buying_players | `int` | verified | How readily he wants players bought. |
| mind_games | `int` | verified | How much he plays on an opponent's mind. |
| flexibility | `int` | verified | How willing he is to change an approach. |
| hardness_of_training | `int` | verified | How hard he wants the side trained. |
| squad_rotation | `int` | verified | How much he wants the side rotated. |
| tempo | `int` | verified | How quickly he wants the side to play. |
| width | `int` | verified | How wide he wants the side to play. |

## Stage

One stage of one competition: a league season, a cup round, or one leg of a tie.

| field | type | status | description |
|---|---|---|---|
| id | `int` | verified | The stage id, which every fixture, league-table group and per-match record joins through. |
| competition_id | `int \| None` | verified | Id of the competition this stage belongs to, in the stage id space; None when the row stores no competition, and None for the one out-of-band id every save carries, which is a marker rather than a competition. |
| competition_name | `str \| None` | unconfirmed | Denormalised name of competition_id, which is None unless a name map is supplied, because the save stores no competition names (unconfirmed). |
| group_id | `int \| None` | verified | Id of the group or section within the competition, or None when the stage has none. |
| round | `Optional[common.CodedValue[competitions.CompetitionRound]]` | verified | The stage's round, or None when the stage has no round, as a league matchday and a league phase do not. Codes with no confirmed meaning keep their raw number and are labelled UNKNOWN. |
| previous_stage_id | `int \| None` | unconfirmed | The stage id the row claims comes before this one; None when the row stores the missing value. It equals `id - 1` on every row seen, and the reader's own row test requires that, so it is not independent evidence of a chain between stages (unconfirmed). |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning. "s25" is data, not a sentinel: it takes small values on several hundred rows per save. "s29" is the missing value on almost every row and carries small numbers on the rest (unconfirmed). |

## Suspension

One unserved suspension, with its player and the club the player belongs to.

| field | type | status | description |
|---|---|---|---|
| player_uid | `int` | unconfirmed | Uid of the suspended player, copied from the decoded player (unconfirmed). |
| player_name | `str \| None` | unconfirmed | Denormalised name of player_uid (unconfirmed). |
| club_uid | `int \| None` | unconfirmed | Uid of the club the player belongs to, which for a player registered with a team another club controls is that controlling club; None for a free agent or a team that does not resolve to a club. Copied from the decoded player (unconfirmed). It is the club the player belongs to **now**, which for an old ban need not be the club he was banned at. |
| club_name | `str \| None` | unconfirmed | Denormalised full name of club_uid (unconfirmed). |
| scope | `<enum 'SuspensionScope'>` | verified | What the ban covers: one competition, a whole nation, or UNKNOWN for a scope code never measured. |
| scope_code | `int` | verified | The scope code exactly as the save stores it: 1 for a competition-wide ban, 5, 6 or 10 for a nation-wide one. What separates 5, 6 and 10 is not known. |
| competition_id | `int \| None` | verified | Id of the competition the ban applies to, in the **stage** id space, so it joins `stages()`, `competitions()`, `fixtures()`, `league_tables()` and `player_match_stats()`. None unless the scope is COMPETITION. |
| competition_name | `str \| None` | unconfirmed | Denormalised name of competition_id, which is None unless a name map is supplied, because the save stores no competition names. A competition the game itself created during the career has a database id no name source outside the save carries, so some rows stay unnamed even with a full map (unconfirmed). |
| nation_id | `int \| None` | verified | Save-local id of the nation whose competitions the ban covers, in the same id space as `Club.nation_id` and `Player.nation_id`. None unless the scope is NATION. |
| issued_date | `date` | verified | Date the ban was issued. |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning (unconfirmed). |

## Tactic

One stored copy of one tactic, belonging to one team.

| field | type | status | description |
|---|---|---|---|
| club_uid | `int \| None` | unconfirmed | Uid of the club the team plays for, None for a team no club lists (unconfirmed). |
| club_name | `str \| None` | unconfirmed | Denormalised full name of club_uid (unconfirmed). |
| team_id | `int` | unconfirmed | The team the copy belongs to, as the save stores it (unconfirmed). |
| team_slot | `int \| None` | unconfirmed | The team's place in that club's own team list, 0 for its first team; None when the team resolves to no club (unconfirmed). |
| index | `int` | unconfirmed | The copy's place among the team's own tactics, counting from zero in stored order. Nothing stored says which of them is selected (unconfirmed). |
| name | `str` | unconfirmed | Stored tactic name (unconfirmed). |
| style_name | `str` | unconfirmed | The tactical style shown with the tactic, as stored text. No screen has confirmed that this label is the style (unconfirmed). |
| mentality | `common.CodedValue[tactics.Mentality]` | verified | The mentality the tactic is set to; the seven codes the game offers each carry the word it shows for them, and any other code reads UNKNOWN. |
| slots | `tuple[tactics.TacticSlot, ...]` | verified | The eleven positions, in stored order. |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | The 19 team-instruction bytes, one int per byte, and the tactic's four-byte style code as one little-endian int. Byte 2 of the instructions is the mentality and is shipped as `mentality` as well; bytes 0, 3, 4, 5, 7, 17 and 18 are the same on every record measured, and bytes 11 to 15 look bit-packed rather than numeric (unconfirmed). |

## TacticSettingUnit

One 24-byte setting unit of a tactic slot, as two bit fields.

| field | type | status | description |
|---|---|---|---|
| head_byte | `int` | unconfirmed | The byte after the unit's lead bytes, which is 0 on most units and 2 or 10 on the rest (unconfirmed). |
| first_bits | `int` | unconfirmed | The unit's seven-byte bit field as one little-endian int; between none and four of its bits are set (unconfirmed). |
| second_bits_low | `int` | unconfirmed | Bits 0 to 31 of the unit's twelve-byte bit field (unconfirmed). |
| second_bits_middle | `int` | unconfirmed | Bits 32 to 63 of that field (unconfirmed). |
| second_bits_high | `int` | unconfirmed | Bits 64 to 95 of that field. The field is wider than 64 bits, so it ships as three words rather than one int no column type could hold; one or two of its 96 bits are set, always above bit 32 (unconfirmed). |

## TacticSlot

One position of a tactic, in possession and out of possession.

| field | type | status | description |
|---|---|---|---|
| number | `int` | verified | The slot's place in the tactic, 0 for the first. |
| in_possession_positions | `tuple[common.CodedValue[tactics.TacticPosition], ...]` | verified | The positions the in-possession mask sets, in ascending bit number; a bit no screen has shown reads UNKNOWN, and the raw value is always the bit number. |
| in_possession_mask | `int` | verified | The whole in-possession mask, column flags included. |
| in_possession_setting_count | `int` | unconfirmed | How many setting units the in-possession block holds (unconfirmed). |
| in_possession_settings | `tuple[tactics.TacticSettingUnit, ...]` | unconfirmed | Those units, in stored order (unconfirmed). |
| out_of_possession_positions | `tuple[common.CodedValue[tactics.TacticPosition], ...]` | verified | The same for the out-of-possession block, which differs from the in-possession one on some slots of some saves. |
| out_of_possession_mask | `int` | verified | The whole out-of-possession mask. |
| out_of_possession_setting_count | `int` | unconfirmed | How many setting units that block holds (unconfirmed). |
| out_of_possession_settings | `tuple[tactics.TacticSettingUnit, ...]` | unconfirmed | Those units, in stored order (unconfirmed). |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | The two bit fields each block carries besides its units, and the index byte the out-of-possession block carries. The role bits hold exactly one bit and relate to the position's role, but two slots the game shows with different roles can store the same bits, so they are not the role on their own. The index bytes of a record are a permutation of 0 to 10 which is the identity on all but one record measured (unconfirmed). |

## Team

One team in a club's team list.

| field | type | status | description |
|---|---|---|---|
| team_id | `int` | unconfirmed | The team's id, which player records use to name their team (unconfirmed). |
| slot | `int` | unconfirmed | Position in the club's team list, 0 for the first entry. Which side each own slot holds, such as a reserve or youth team, is not known (unconfirmed). |
| club_uid | `int` | unconfirmed | Uid of the club whose record stores this team: the club listing it for its own teams, and the affiliate club itself for an affiliate team (unconfirmed). |
| is_affiliate | `bool` | unconfirmed | Whether the team belongs to an affiliate club the listing club controls (unconfirmed). |

## TeamMatchStats

One team's statistics in one match, as the game's match stats screen shows them.

| field | type | status | description |
|---|---|---|---|
| competition_id | `int` | verified | Id of the competition, as `Fixture.competition_id`. |
| home_team_id | `int` | verified | The home side's team id, as `Fixture.home_team_id`. |
| away_team_id | `int` | verified | The away side's team id, as `Fixture.away_team_id`. |
| date | `date` | verified | The kick-off date, as `Fixture.date`. |
| kick_off_time | `time` | verified | The kick-off time of day, as `Fixture.kick_off_time`. |
| team_id | `int` | verified | The team this row describes, one of the two above. |
| is_home | `bool` | verified | Whether the row describes the home side. |
| detailed_report | `bool` | unconfirmed | Whether the game kept the longer report format for this match. Only that format carries progressive passes (unconfirmed). |
| players | `int` | unconfirmed | Player records in the team's matchday squad, starters and substitutes (unconfirmed). |
| shots | `int` | verified | Shots. |
| shots_on_target | `int` | verified | Shots on target. |
| blocked_shots | `int` | verified | The team's shots that were blocked. |
| shots_outside_box | `int` | verified | Shots from outside the box, which the screen calls long shots. |
| clear_cut_chances | `int` | verified | Clear-cut chances the team had. |
| woodwork | `int` | verified | Shots that hit the woodwork. |
| fouls_made | `int` | verified | Fouls committed. |
| offsides | `int` | verified | Offsides. |
| yellow_cards | `int` | verified | Yellow cards. |
| red_cards | `int` | verified | Red cards. |
| crosses_attempted | `int` | verified | Crosses attempted. |
| crosses_completed | `int` | verified | Crosses completed. |
| tackles_attempted | `int` | verified | Tackles attempted. |
| tackles_completed | `int` | verified | Tackles won. |
| aerial_challenges_attempted | `int` | verified | Aerial challenges attempted. |
| headers_won | `int` | verified | Aerial challenges won. |
| distance_km | `float` | verified | Distance covered by the squad, in kilometres. |
| expected_goals | `float` | verified | Expected goals (xG). |
| non_penalty_expected_goals | `float` | verified | Expected goals from shots other than penalties (npxG). |
| corners | `int` | verified | Corners. |
| passes_attempted | `int` | verified | Passes attempted. |
| passes_completed | `int` | verified | Passes completed. A few rows store more than were attempted, and the game shows them the same way. |
| final_third_passes | `int` | verified | Passes into the final third. |
| progressive_passes | `int \| None` | verified | Progressive passes, or None when the report is not detailed, because the game shows them only for detailed reports. |
| possession_percent | `int` | verified | The team's share of both sides' completed passes, in whole percent. The home share is rounded and the away share is the rest, so a pair sums to 100. |
| ball_distribution_percent | `int` | verified | The screen's ball distribution between players, in whole percent. Each side is rounded half up on its own, so a pair can sum to 101. |

## TeamTraining

One team's training calendar, with the library of schedules the save holds beside it.

| field | type | status | description |
|---|---|---|---|
| team_id | `int` | verified | The team whose calendar this is, as the save stores it. |
| club_uid | `int \| None` | verified | Uid of the club that fields `team_id`, None for a team no club lists. For a team the managed club fields at a club it controls, this is the managed club. |
| club_name | `str \| None` | verified | Denormalised full name of club_uid. |
| team_slot | `int \| None` | unconfirmed | The team's place in that club's own team list, 0 for its first team; None when the team resolves to no club. Which side each slot is, such as a reserve or a youth team, is not known (unconfirmed). |
| weeks | `tuple[training.TrainingWeek, ...]` | verified | Every week of the calendar, in stored order, running from before the save's date to well after it. |
| schedule_library | `tuple[training.TrainingSchedule, ...] \| None` | unconfirmed | The schedules the manager has saved, in stored order, or None when reading the library is unsupported. An empty tuple means an observed empty library. One library is stored per save rather than per team, so every row carries the same one. It holds only saved schedules: the game's own built-in ones are not in it, although a week may well name one. **The save may store a schedule more than once**: most saves measured hold twice as many entries as the Schedules screen lists, the same schedules over under two runs of ids, so count the distinct `(folder, name)` pairs rather than the entries to compare with a screen (unconfirmed). |

## TrainingDay

One day of a week of a team's training calendar.

| field | type | status | description |
|---|---|---|---|
| day | `datetime.date \| None` | verified | The date, which is the week's start plus the day's place in the week; None when the week's start does not decode. |
| sessions | `tuple[common.CodedValue[training.TrainingSession], ...]` | unconfirmed | The day's three sessions in the order the Training screen lists them, top to bottom. On an FM26 save every session is UNKNOWN with its raw code (unconfirmed). |

## TrainingSchedule

One schedule the save keeps in the manager's own library of saved schedules.

| field | type | status | description |
|---|---|---|---|
| folder | `str` | unconfirmed | The folder the schedule is filed under (unconfirmed). |
| name | `str` | unconfirmed | The schedule's name (unconfirmed). |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning: the id the save stores with the schedule, which is not the key a week's name is matched on. Where the save stores the same schedule twice, the copies differ only in this id (unconfirmed). |

## TrainingWeek

One week of a team's training calendar.

| field | type | status | description |
|---|---|---|---|
| week_start | `datetime.date \| None` | verified | The day the week starts, None when the stored date does not decode. |
| schedule_name | `str` | verified | Name of the schedule the week runs, exactly as the save holds it. A schedule is a user's own file, so this is whatever it was called. |
| days | `tuple[training.TrainingDay, ...]` | verified | The week's seven days in calendar order, starting on `week_start`. Empty when a week is built from only its start and name. |

## TransferWindow

One transfer window: when it opens and closes, relative to the season start.

| field | type | status | description |
|---|---|---|---|
| start_day | `int` | verified | Day of the month the window opens, 1 to 31. |
| start_month | `int` | verified | Month the window opens, 1 to 12. |
| start_season_year_offset | `int` | verified | Which season year the window opens in: 0 is the season's own start year and 1 the calendar year after it. There is no calendar date without a season, so this is an offset and never a date. |
| end_day | `int` | verified | Day of the month the window closes, 1 to 31. |
| end_month | `int` | verified | Month the window closes, 1 to 12. |
| end_season_year_offset | `int` | verified | Which season year the window closes in, as start_season_year_offset. |
| unknown | `collections.abc.Mapping[str, int]` | unconfirmed | Numeric fields with no known meaning. "close_time" is the value stored against the window's closing-time tag, which looks like an hour and minute on a 24-hour clock but is not named, because the game's own Rules screen shows no time of day to pin it to. "window_type" is a small code the record carries on about two windows in five and no displayed label explains (unconfirmed). |

## ValidationReport

What `validate_save` found, holding no names, uids or other values from the save.

| field | type | status | description |
|---|---|---|---|
| fmsave_version | `str` |  | The fmsave version. |
| python_version | `str` |  | The Python version. |
| os | `str` |  | The operating system name, for example "Linux". |
| game | `str` |  | Game edition, for example "FM26". |
| build | `str` |  | Version and build that last wrote the save. |
| known_build | `bool` |  | Whether fmsave has a layout registered for every reader for this build. It describes layout coverage. See `field_statuses` for field verification. It is False for an FM27 build that borrows another build's layouts. |
| section_schemas | `collections.abc.Mapping[str, int]` |  | Schema number of every named section. |
| readers | `tuple[fmsave._checks.ReaderValidation, ...]` |  | Each reader's outcome, in the order they ran. |
| field_statuses | `collections.abc.Mapping[str, str]` |  | Whether each public field's meaning is "verified" or "unconfirmed". |
| experimental_counts | `collections.abc.Mapping[str, int]` |  |  |


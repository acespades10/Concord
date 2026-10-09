import { BookOpen, GitCompareArrows, Shapes, Tag } from "lucide-react";

export default function GuidePage() {
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">A LITTLE CLARITY GOES A LONG WAY</span>
          <h1>
            The field guide<span className="heading-dot">.</span>
          </h1>
          <p>
            Everything your team needs to make thoughtful, consistent decisions.
          </p>
        </div>
        <BookOpen size={32} className="subtle-icon" />
      </div>
      <div className="guide-intro panel">
        <h2>Different perspectives. One shared standard.</h2>
        <p>
          Concord brings independent human judgments together, measures their
          agreement, and gives reviewers the context to resolve differences.
          Annotators see only their own work, so each decision starts with a
          fresh perspective.
        </p>
        <ol>
          <li>
            <strong>Set the standard.</strong> Admins create a draft project,
            configure labels, add annotators, and import JSONL or CSV.
          </li>
          <li>
            <strong>Open the queue.</strong> Activation locks the rules. Each
            item goes to the configured number of independent raters.
          </li>
          <li>
            <strong>Make your judgment.</strong> Claims last 15 minutes and
            renew with every saved draft. Submitted annotations are final.
          </li>
          <li>
            <strong>Find common ground.</strong> Reviewers see live agreement,
            compare submissions, and adjudicate uncertain items.
          </li>
          <li>
            <strong>Put your data to work.</strong> Export raw submissions,
            resolved consensus, or both.
          </li>
        </ol>
      </div>
      <div className="project-grid guide-cards">
        <section className="panel">
          <span className="project-icon lavender">
            <Tag size={22} />
          </span>
          <h2>Response rating</h2>
          <p>
            Read the prompt and response, then choose one configured label. An
            optional note helps explain your reasoning.
          </p>
          <p>
            Ordered scales preserve label order. Agreement is measured using
            unweighted categorical kappa.
          </p>
        </section>
        <section className="panel">
          <span className="project-icon peach">
            <Shapes size={22} />
          </span>
          <h2>Entity annotation</h2>
          <p>
            Pick an entity type and select the first and last token. Select one
            token twice to label a single-token entity.
          </p>
          <p>
            Spans cannot overlap. Empty spans are valid when no entities are
            present. Offsets count Unicode code points.
          </p>
        </section>
        <section className="panel">
          <span className="project-icon blue">
            <GitCompareArrows size={22} />
          </span>
          <h2>A/B comparison</h2>
          <p>
            Compare anonymous responses and prefer A, prefer B, or call a tie.
            Display order is randomized per assignment.
          </p>
          <p>
            Reviewers and exports use canonical A/B identities, so agreement is
            measured consistently.
          </p>
        </section>
      </div>
      <div className="quality-grid">
        <section className="panel">
          <h2>When does an item need review?</h2>
          <p>
            Consensus needs a strict majority and must meet the project’s
            vote-share threshold after all required raters submit. With three
            raters and an 80% threshold, two votes are not enough.
          </p>
          <p>
            NER uses exact majority spans and checks support at every BIO token,
            including unmarked text. The minimum support is the item’s vote
            share. Ties and ambiguous boundaries go to review.
          </p>
          <p>
            A reviewer’s final decision takes precedence over automatic
            consensus. Their rationale travels with consensus exports.
          </p>
        </section>
        <section className="panel">
          <h2>Reading agreement with care</h2>
          <p>
            Fleiss’ kappa measures agreement across fully rated items. Cohen’s
            kappa compares pairs of annotators on their shared work. NER
            additionally reports exact-span F1.
          </p>
          <p>
            Undefined kappa is displayed with a reason, never as a misleading
            zero. If everyone uses only one category, expected disagreement is
            zero and kappa cannot be calculated.
          </p>
          <p>
            Use scores to find questions worth discussing, alongside the
            underlying annotations.
          </p>
        </section>
      </div>
    </>
  );
}

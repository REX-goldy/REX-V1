import { useMemo, useState } from "react";
import { BookOpen, ExternalLink, Search } from "lucide-react";
import {
  ARTICLES,
  CATEGORIES,
  GLOSSARY,
  articleById,
  searchHandbook,
  type HandbookArticle,
  type HandbookCategory,
} from "../content/handbook";
import { EmptyState, PageHeader, StatusPill } from "../components/Primitives";

type CategoryFilter = "all" | HandbookCategory;

function Section({
  id,
  index,
  title,
  paragraphs,
}: {
  id: string;
  index: string;
  title: string;
  paragraphs: string[];
}) {
  return (
    <section className="handbook-section" id={id}>
      <div className="handbook-section-head">
        <span className="handbook-section-index">{index}</span>
        <h3>{title}</h3>
      </div>
      {paragraphs.map((paragraph) => (
        <p key={paragraph}>{paragraph}</p>
      ))}
    </section>
  );
}

function ArticleView({
  article,
  onSelect,
}: {
  article: HandbookArticle;
  onSelect: (id: string) => void;
}) {
  const sections = [
    { id: "definition", title: "Definition", paragraphs: article.definition },
    { id: "why", title: "Why it matters", paragraphs: article.why },
    { id: "example", title: "Example", paragraphs: article.example },
    { id: "rex", title: "How REX uses it", paragraphs: article.rex },
    { id: "mistakes", title: "Common mistakes", paragraphs: article.mistakes },
  ];

  return (
    <article className="handbook-article" id="handbook-article-top">
      <div className="handbook-article-head">
        <div className="handbook-article-breadcrumb">
          {CATEGORIES.find((category) => category.id === article.category)?.label}
        </div>
        <h2>{article.title}</h2>
        <p>{article.summary}</p>
        <div className="handbook-article-tags">
          <StatusPill tone="neutral">{article.category.replace("-", " ")}</StatusPill>
          <StatusPill tone="gold">{article.related.length} related</StatusPill>
        </div>
      </div>

      <nav className="handbook-toc" aria-label="Article contents">
        <span className="handbook-toc-label">Contents</span>
        {sections.map((section, index) => (
          <a key={section.id} href={`#${section.id}`}>
            {String(index + 1).padStart(2, "0")} {section.title}
          </a>
        ))}
        {article.deepDive?.map((section, index) => (
          <a key={section.heading} href={`#deep-${index}`}>
            {String(sections.length + index + 1).padStart(2, "0")} {section.heading}
          </a>
        ))}
        <a href="#related">Related</a>
      </nav>

      <div className="handbook-article-body">
        {sections.map((section, index) => (
          <Section
            key={section.id}
            id={section.id}
            index={String(index + 1).padStart(2, "0")}
            title={section.title}
            paragraphs={section.paragraphs}
          />
        ))}
        {article.deepDive?.map((section, index) => (
          <Section
            key={section.heading}
            id={`deep-${index}`}
            index={String(sections.length + index + 1).padStart(2, "0")}
            title={section.heading}
            paragraphs={section.body}
          />
        ))}

        <section className="handbook-section" id="related">
          <div className="handbook-section-head">
            <span className="handbook-section-index">↗</span>
            <h3>Related concepts</h3>
          </div>
          <div className="handbook-related">
            {article.related.map((id) => {
              const related = articleById(id);
              if (!related) return null;
              return (
                <button key={id} className="handbook-related-link" onClick={() => onSelect(id)}>
                  <span>
                    <span className="handbook-related-title">{related.title}</span>
                    <span className="handbook-related-copy">{related.summary}</span>
                  </span>
                  <ExternalLink size={13} strokeWidth={1.5} />
                </button>
              );
            })}
          </div>
        </section>
      </div>
    </article>
  );
}

export function HandbookPage({
  initialArticle,
  onSelectArticle,
}: {
  initialArticle: string;
  onSelectArticle: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<CategoryFilter>("all");
  const [showGlossary, setShowGlossary] = useState(false);

  const selected = articleById(initialArticle) ?? ARTICLES[0];

  const filtered = useMemo(() => {
    const results = searchHandbook(query);
    return category === "all"
      ? results
      : results.filter((article) => article.category === category);
  }, [query, category]);

  const glossaryMatches = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return GLOSSARY;
    return GLOSSARY.filter(
      (entry) =>
        entry.term.toLowerCase().includes(value) ||
        entry.definition.toLowerCase().includes(value),
    );
  }, [query]);

  return (
    <div className="stack">
      <PageHeader
        eyebrow="Help & handbook · built-in reference"
        title="Learn the language before trusting the number."
        subtitle="A structured handbook for trading, technical analysis, risk, statistics, and the actual REX implementation. Every implementation claim is checked against the codebase."
        actions={
          <div className="handbook-search">
            <Search size={14} strokeWidth={1.5} />
            <input
              className="input"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setShowGlossary(false);
              }}
              placeholder="Search articles, concepts, metrics…"
              aria-label="Search handbook"
            />
          </div>
        }
      />

      <div className="handbook-layout">
        <aside className="handbook-categories" aria-label="Handbook categories">
          <button
            className={`handbook-category ${category === "all" && !showGlossary ? "active" : ""}`}
            onClick={() => {
              setCategory("all");
              setShowGlossary(false);
            }}
          >
            <span>All topics</span>
            <span className="handbook-count">{ARTICLES.length}</span>
          </button>
          {CATEGORIES.map((item) => (
            <button
              key={item.id}
              className={`handbook-category ${category === item.id && !showGlossary ? "active" : ""}`}
              onClick={() => {
                setCategory(item.id);
                setShowGlossary(false);
              }}
            >
              <span>
                {item.label}
                <small>{item.blurb}</small>
              </span>
              <span className="handbook-count">
                {ARTICLES.filter((article) => article.category === item.id).length}
              </span>
            </button>
          ))}
          <button
            className={`handbook-category ${showGlossary ? "active" : ""}`}
            onClick={() => setShowGlossary(true)}
          >
            <span>
              Glossary
              <small>Core terminology</small>
            </span>
            <span className="handbook-count">{GLOSSARY.length}</span>
          </button>
        </aside>

        <section className="handbook-list" aria-label="Articles">
          <div className="handbook-list-head">
            <span>{showGlossary ? "Glossary" : "Articles"}</span>
            <span className="mono">{showGlossary ? glossaryMatches.length : filtered.length}</span>
          </div>
          {showGlossary ? (
            <div className="handbook-glossary-list">
              {glossaryMatches.map((entry) => (
                <button
                  key={entry.term}
                  className="handbook-list-item"
                  onClick={() => {
                    onSelectArticle(entry.article);
                    setShowGlossary(false);
                  }}
                >
                  <span className="handbook-list-title">{entry.term}</span>
                  <span className="handbook-list-summary">{entry.definition}</span>
                </button>
              ))}
              {!glossaryMatches.length ? (
                <p className="handbook-empty">No glossary terms match “{query}”.</p>
              ) : null}
            </div>
          ) : filtered.length ? (
            filtered.map((article) => (
              <button
                key={article.id}
                className={`handbook-list-item ${article.id === selected.id ? "active" : ""}`}
                onClick={() => onSelectArticle(article.id)}
              >
                <span className="handbook-list-title">{article.title}</span>
                <span className="handbook-list-summary">{article.summary}</span>
              </button>
            ))
          ) : (
            <div style={{ padding: 16 }}>
              <EmptyState
                title="No matching articles"
                copy={`Nothing in this category matches “${query}”. Try a broader term or clear the search.`}
              />
            </div>
          )}
        </section>

        {showGlossary ? (
          <article className="handbook-article">
            <div className="handbook-article-head">
              <div className="handbook-article-breadcrumb">Reference</div>
              <h2>Glossary</h2>
              <p>Short definitions for the terms used across the terminal and the handbook.</p>
            </div>
            <div className="handbook-article-body">
              <div className="handbook-section">
                <div className="handbook-section-head">
                  <span className="handbook-section-index">
                    <BookOpen size={15} strokeWidth={1.5} />
                  </span>
                  <h3>Terms</h3>
                </div>
                <div className="glossary-grid">
                  {glossaryMatches.map((entry) => (
                    <button
                      key={entry.term}
                      className="glossary-card"
                      onClick={() => {
                        onSelectArticle(entry.article);
                        setShowGlossary(false);
                      }}
                    >
                      <strong>{entry.term}</strong>
                      <span>{entry.definition}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </article>
        ) : (
          <ArticleView article={selected} onSelect={(id) => onSelectArticle(id)} />
        )}
      </div>
    </div>
  );
}

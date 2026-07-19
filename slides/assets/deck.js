/*
 * TemporalDeck — shared reveal.js bootstrap for the workshop decks.
 *
 * Slides are authored as inline HTML (skill scaffold), and Mermaid diagrams
 * are inline <div class="mermaid"> blocks — so there is no Markdown/highlight
 * step and therefore none of the source-pollution that plagues the
 * ```mermaid-in-Markdown path. We only initialize Reveal + Mermaid, wait for
 * fonts, then render.
 *
 * Plain browser globals (Reveal, RevealNotes, mermaid) from UMD builds — no
 * build step, git-friendly static site.
 */
(function (global) {
  "use strict";

  /* Mermaid theme variables tuned to the Temporal dark palette in theme.css. */
  var MERMAID_THEME_VARIABLES = {
    darkMode: true,
    background: "transparent",
    primaryColor: "#151a2e",
    primaryBorderColor: "#3a4266",
    primaryTextColor: "#e7eaf5",
    lineColor: "#8890b5",
    secondaryColor: "#1b2140",
    tertiaryColor: "#161c34",
    clusterBkg: "transparent",
    clusterBorder: "#3a4266",
    // Transparent so edge labels never mask the connector line behind them.
    edgeLabelBackground: "transparent",
    fontSize: "15px",
    // Sequence-diagram notes: dark card instead of the default cream.
    noteBkgColor: "#151a2e",
    noteTextColor: "#e7eaf5",
    noteBorderColor: "#4ce0a0",
    actorBkg: "#0d1b33",
    actorBorder: "#3b82f6",
    actorTextColor: "#cfe0ff",
    signalColor: "#9aa2bd",
    signalTextColor: "#e7eaf5",
  };

  /*
   * Persistent furniture: a bottom-left Temporal mark on .reveal (outside
   * .slides) so it stays put across slide transitions. The bottom-right slide
   * number is reveal's built-in slideNumber.
   */
  function injectFurniture() {
    var reveal = document.querySelector(".reveal");
    if (!reveal || reveal.querySelector(".deck-logo")) {
      return;
    }
    var logo = document.createElement("img");
    logo.className = "deck-logo";
    logo.src = "assets/temporal-mark.png";
    logo.alt = "Temporal";
    reveal.appendChild(logo);
  }

  function init() {
    // Neutralize mermaid auto-run and apply our theme before rendering.
    if (typeof global.mermaid !== "undefined") {
      try {
        global.mermaid.initialize({
          startOnLoad: false,
          securityLevel: "loose",
          theme: "base",
          fontFamily: "'Inter', system-ui, sans-serif",
          themeVariables: MERMAID_THEME_VARIABLES,
          flowchart: {
            useMaxWidth: true,
            htmlLabels: true,
            // 'linear' (not 'basis'): basis curves break edge-label placement
            // ("Could not find a suitable point for the given distance").
            curve: "linear",
            padding: 12,
          },
          sequence: { useMaxWidth: true },
        });
      } catch (err) {
        console.error("TemporalDeck: mermaid.initialize failed", err);
      }
    }

    Reveal.initialize({
      width: 1280,
      height: 720,
      margin: 0.04,
      center: false, // per-slide-type layout is handled in theme.css
      hash: true,
      slideNumber: "c",
      transition: "fade",
      transitionSpeed: "fast",
      controls: true,
      progress: true,
      plugins: [RevealNotes],
    });

    injectFurniture();

    // Render diagrams once the deck is ready and the web font has loaded —
    // Mermaid measures node boxes with the final font, avoiding clipped labels.
    Reveal.on("ready", function () {
      renderDiagrams();
    });
  }

  /* Decode the HTML entities the browser adds when serializing innerHTML,
   * so Mermaid gets its original source (&amp; -> &, &lt; -> <, &gt; -> >). */
  function decodeEntities(text) {
    return text
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/&amp;/g, "&");
  }

  /*
   * Render each inline <div class="mermaid"> with mermaid.render(), which draws
   * in Mermaid's own off-DOM sandbox and is therefore independent of the host
   * element's size. mermaid.run() cannot be used here: it renders in place, and
   * diagrams on non-active reveal slides have zero dimensions, which makes
   * dagre fail ("Could not find a suitable point for the given distance").
   * We wait for fonts first so label boxes are measured with the final font.
   */
  async function renderDiagrams() {
    if (typeof global.mermaid === "undefined") {
      return;
    }
    if (document.fonts && document.fonts.ready) {
      try {
        await document.fonts.ready;
      } catch (err) {
        console.warn("TemporalDeck: document.fonts.ready rejected", err);
      }
    }
    var nodes = document.querySelectorAll(".reveal .mermaid");
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      if (el.dataset.rendered === "true") {
        continue;
      }
      var source = decodeEntities(el.innerHTML).trim();
      try {
        var result = await global.mermaid.render("deck-mermaid-" + i, source);
        el.innerHTML = result.svg;
        el.dataset.rendered = "true";
      } catch (err) {
        console.error("TemporalDeck: mermaid render failed for diagram " + i, err);
      }
    }
  }

  global.TemporalDeck = { init: init };
})(window);

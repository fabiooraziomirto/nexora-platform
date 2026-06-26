%% svjour3-stub.cls — DEVELOPMENT STUB ONLY
%%
%% Minimal shim that makes main.tex compile for writing/review.
%% Does NOT produce correct Springer formatting.
%%
%% BEFORE SUBMISSION: replace with official svjour3.cls from:
%%   https://www.springer.com/gp/livingreviews/latex-templates
%%
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{svjour3}[2024/01/01 Springer svjour3 stub for development]

\DeclareOption{twocolumn}{\PassOptionsToClass{twocolumn}{article}}
\DeclareOption{onecolumn}{\PassOptionsToClass{onecolumn}{article}}
\DeclareOption{smallextended}{}
\DeclareOption{small}{}
\DeclareOption{large}{}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax

\LoadClass[10pt,a4paper]{article}

\usepackage{geometry}
\geometry{a4paper, top=2cm, bottom=2.5cm, left=1.8cm, right=1.8cm, columnsep=5mm}
\usepackage{times}

% ── svjour3 title/author commands ─────────────────────────────────────────────
\newcommand{\titlerunning}[1]{}
\newcommand{\authorrunning}[1]{}
\newcommand{\journalname}[1]{\gdef\@journalname{#1}}
\gdef\@journalname{}
\newcommand{\smartqed}{}
\newcommand{\email}[1]{\texttt{#1}}
\newcommand{\PACS}[1]{}
\newcommand{\MSC}[1]{}
\newcommand{\at}{\\\quad}

% Institute
\newcommand{\institute}[1]{\gdef\@institute{#1}}
\gdef\@institute{}

% \keywords: redefines \and locally so "kw1 \and kw2" renders as "kw1, kw2"
\newcommand{\keywords}[1]{%
  \par\vspace{4pt}\noindent\textbf{Keywords:}\ %
  \begingroup
    \def\and{, }%
    #1%
  \endgroup
  \par
}

% abstract: simple indented block, avoids \list which conflicts with \and
\renewenvironment{abstract}{%
  \small
  \begin{center}\textbf{Abstract}\end{center}%
  \begin{quotation}\noindent\ignorespaces
}{%
  \end{quotation}
}

% Patch \maketitle to print institute below authors
\let\svj@orig@maketitle\maketitle
\renewcommand{\maketitle}{%
  \svj@orig@maketitle
  \ifx\@institute\@empty\else
    \begin{center}\small\itshape\@institute\end{center}%
  \fi
}

\endinput

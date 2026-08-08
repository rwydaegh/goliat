% 
% This is file `iopjournal.cls'
%
% This file is distributed in the hope that it will be useful, 
% but WITHOUT ANY WARRANTY; without even the implied warranty of 
% MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
%
% IOP Publishing Ltd
%
% email: customerservices@ioppublishing.org
%
% Copyright 2025 IOP Publishing Ltd.
%
% This work may be distributed and/or modified under the
% conditions of the LaTeX Project Public License, either version 1.3c
% of this license or (at your option) any later version.
% The latest version of this license is in
%   http://www.latex-project.org/lppl.txt
% and version 1.3c or later is part of all distributions of LaTeX
% version 2005/12/01 or later.
% 
% This work has the LPPL maintenance status `maintained'.
% 
% The Current Maintainer of this work is IOP Publishing Ltd.
%


\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{iopjournal}[2024/01/31 IOP Publishing journal article LaTeX template]

%Packages that the class file relies on

\RequirePackage{fancyhdr}

\RequirePackage{xcolor}

\RequirePackage{graphicx}


%Options for the class file

\newif\if@anonymous
\@anonymousfalse
\DeclareOption{anonymous}{\@anonymoustrue}

%\DeclareOption{...}{...}

%Pass any undefined options on to the article class
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}

%Execute the options
\ProcessOptions\relax

%Load the article class as the basis for the formatting
\LoadClass[a4paper]{article}

\RequirePackage[colorlinks=true, allcolors=blue]{hyperref}

%Define the text area
\setlength\voffset{-25mm}
%\setlength\hoffset{-10mm}
%\setlength\topmargin{10mm}
\setlength\headsep{10mm}
\setlength\footskip{12mm}
\setlength\marginparwidth{25mm}
\setlength\marginparsep{2mm}
\setlength\textwidth{153mm}
\setlength\textheight{255mm}

%General text options, will apply unless commands specify otherwise
\raggedright
\setlength\parindent{15pt} 

%Headers and footers
\pagestyle{fancy}
\fancyhfoffset[L]{27mm}
\fancyhead[L]{{\small \sf IOP Publishing}\hspace{5mm} {\it Phys. Med. Biol.} {\bf vv} (yyyy) aaaaaa}
\fancyhead[C]{}
\fancyhead[R]{Wydaeghe {\it et al}\ }
\fancyfoot[LR]{}
\fancyfoot[C]{\thepage}
\renewcommand{\headrulewidth}{0.5pt}
\renewcommand{\footrulewidth}{0.5pt}
\renewcommand{\headrule}{\color{gray}\if@fancyplain\let\headrulewidth\plainheadrulewidth\fi
      \hrule\@height\headrulewidth\@width\headwidth
      \vskip-\headrulewidth}
\renewcommand{\footrule}{{\color{gray}\if@fancyplain\let\footrulewidth\plainfootrulewidth\fi
    \vskip-\footruleskip\vskip-\footrulewidth
    \hrule\@width\headwidth\@height\footrulewidth\vskip\footruleskip}}

%Article title, type and left-column content

\newcommand{\articletype}[1]{{\vspace*{-8mm}\noindent \Large \sf Journal Name}

\vspace*{8mm} \noindent\reversemarginpar
\marginpar{\vspace{-3mm} {\color{gray}\hrule} \ \\ Crossmark\\ {\color{gray}\hrule} \ \\ \tiny {\sf RECEIVED} {\small \\ dd Month yyyy}\\ \\ {\sf REVISED} {\small \\ dd Month yyyy}}{\scriptsize \sf{\bfseries \MakeUppercase{#1}}}}

\renewcommand{\title}[1]{{\exhyphenpenalty=10000\hyphenpenalty=10000 
 \fontsize{18}{21}\selectfont\noindent\raggedright
        \textsf{#1}\par}\suppressfloats[t]}

		
\renewcommand{\author}[1]{{\vspace{5mm}%
   \fontsize{10}{12}
      \raggedright \if@anonymous Author list removed for anonymity \else #1 \fi
	  \vspace{3mm}}}

\newcommand{\affil}[1]{{\fontsize{8}{10}\selectfont
       \raggedright \if@anonymous \phantom{#1} \else #1 \fi}
	   }

\newcommand{\email}[1]{\vspace*{12pt}{\fontsize{8}{10}\selectfont
       \raggedright {\bfseries E-mail:} \if@anonymous \phantom{#1} \else #1 \fi}
	  \vspace{3mm} }
	   
\newcommand{\keywords}[1]{{\fontsize{8}{10}\selectfont
       \raggedright {\bfseries Keywords:} #1}
	  }

\renewenvironment{abstract}{%
      \vspace{16pt plus3pt minus3pt}
      {\color{gray}\hrule} \ \\
      \noindent \fontsize{11}{12}\selectfont {\bfseries Abstract}\\
	  \rm\ignorespaces \raggedright}{\vspace{3mm} {\color{gray}\hrule}}


% Section titles
	
\renewcommand\section{\@startsection {section}{1}{\z@}%
                   {-3.25ex\@plus -1ex \@minus -.2ex}%
                   {1sp}%
                   {\reset@font\normalsize\bfseries\raggedright}}
\renewcommand\subsection{\@startsection{subsection}{2}{\z@}%
                   {-3.25ex\@plus -1ex \@minus -.2ex}%
                   {1sp}%
                   {\reset@font\normalsize\itshape\raggedright}}
\renewcommand\subsubsection{\@startsection{subsubsection}{3}{\z@}%
                                     {-3.25ex\@plus -1ex \@minus -.2ex}%
                                     {-1em \@plus .2em}%
                                     {\reset@font\normalsize\itshape}}


% New command for acknowledgments to enable automatic removal when anonymous option is used

\newcommand{\ack}[1]{
\section*{Acknowledgments}
\if@anonymous Removed for anonymity \else #1 \fi}

\newcommand{\funding}[1]{
\section*{Funding}
\if@anonymous Removed for anonymity \else #1 \fi}

\newcommand{\data}[1]{
\section*{Data availability}
\if@anonymous Removed for anonymity \else #1 \fi}

\newcommand{\roles}[1]{
\section*{Author contributions}
\if@anonymous Removed for anonymity \else #1 \fi}

\newcommand{\suppdata}[1]{
\section*{Supplementary data}
#1}

%Figure captions

\renewcommand{\@makecaption}[2]{\vskip\abovecaptionskip
\sbox\@tempboxa{\fontsize{8}{10}\selectfont {\bfseries #1.} #2}%
\ifdim \wd\@tempboxa >\hsize
\raggedright \fontsize{8}{10}\selectfont {\bfseries #1.} #2\par
\else
\global \@minipagefalse
\hb@xt@\hsize{\hfil\box\@tempboxa\hfil}%
\fi
\vskip\belowcaptionskip}

%Table font style
\let\oldtabular\tabular
\renewcommand{\tabular}{\fontsize{8}{10}\selectfont \oldtabular}

%ORCID

\newcommand{\orcid}[1]{\href{https://orcid.org/#1}{\includegraphics[width=8pt]{orcid}}}

\endinput
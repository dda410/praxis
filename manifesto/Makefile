SRC := reality-first.org
PDF := reality-first.pdf

PANDOC    := pandoc
PDFENGINE := xelatex

.PHONY: all pdf view clean

all: pdf

pdf: $(PDF)

$(PDF): $(SRC) header.tex
	$(PANDOC) $(SRC) \
		--from=org \
		--pdf-engine=$(PDFENGINE) \
		--toc --toc-depth=2 \
		--number-sections \
		-H header.tex \
		-V geometry:a4paper,margin=2.5cm \
		-V mainfont="Latin Modern Roman" \
		-V monofont="DejaVu Sans Mono" \
		-V monofontoptions="Scale=0.85" \
		-V fontsize=11pt \
		-V lang=en \
		-V documentclass=article \
		-V colorlinks=true \
		-V linkcolor=black \
		-V urlcolor=blue \
		-V toccolor=black \
		-o $(PDF)

view: $(PDF)
	xdg-open $(PDF) >/dev/null 2>&1 &

clean:
	rm -f $(PDF) *.aux *.log *.out *.toc

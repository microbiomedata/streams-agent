# Gut Microbiome Diversity in Urban and Rural Populations of Eastern Kenya

**Authors:** Jane Muthoni, Peter Ochieng, Sarah Kimani, David Njoroge

**Journal:** Environmental Microbiome, 2025, 20(1):42

**DOI:** 10.1186/s40793-025-00042-7

## Abstract

The gut microbiome plays a critical role in human health, yet most studies have focused on Western populations. Here we characterize the gut microbiome of 120 adults from urban (Nairobi, n=60) and rural (Tharaka-Nithi County, n=60) settings in eastern Kenya using 16S rRNA gene amplicon sequencing of the V4 region. Rural participants exhibited significantly higher alpha diversity (Shannon index 4.2 vs 3.1, p<0.001) and distinct community composition dominated by Prevotella, while urban participants showed increased Bacteroides abundance consistent with a more westernized diet. We identified 12 amplicon sequence variants uniquely associated with rural subsistence farming lifestyles. These findings highlight the need for geographically diverse microbiome reference datasets.

## Introduction

The human gut microbiome is a complex ecosystem of trillions of microorganisms that influences host metabolism, immune function, and disease susceptibility (Lynch & Pedersen, 2016). Despite growing recognition of its importance, the majority of gut microbiome research has been conducted in North American and European cohorts, leaving significant gaps in our understanding of microbiome variation across diverse human populations (Pasolli et al., 2019).

Sub-Saharan Africa presents a particularly interesting context for microbiome research due to diverse dietary patterns ranging from traditional plant-based diets to rapidly westernizing urban diets (De Filippo et al., 2010). Prior studies in Burkina Faso, Tanzania, and South Africa have demonstrated substantial differences in gut microbiome composition between rural and urban populations (Schnorr et al., 2014).

Kenya, with its rapid urbanization and diverse ethnic and dietary landscape, provides an ideal setting to examine how lifestyle transitions affect the gut microbiome. In this study, we compare gut microbial communities between urban residents of Nairobi and rural inhabitants of Tharaka-Nithi County in eastern Kenya.

### Study Objectives

1. Characterize and compare gut microbiome diversity between urban and rural Kenyan populations
2. Identify microbial taxa associated with rural versus urban lifestyles
3. Evaluate the relationship between dietary patterns and microbiome composition

## Methods

### Study Design and Participants

This cross-sectional study enrolled 120 healthy adults aged 25-55 years between March and August 2024. Participants were recruited from two sites: Nairobi (urban, n=60) and Tharaka-Nithi County (rural, n=60). Inclusion criteria required participants to have resided in their respective settings for at least 5 years and to have not taken antibiotics in the preceding 3 months.

The study was approved by the Kenya Medical Research Institute (KEMRI) Ethics Review Committee (protocol KEMRI/SERU/2024/4201). Written informed consent was obtained from all participants.

### Sample Collection

Stool samples were self-collected by participants using provided sterile collection kits (OMNIgene-GUT, DNA Genotek). Samples were transported on ice to the KEMRI laboratory within 24 hours of collection and stored at -80°C until processing.

### DNA Extraction

Total genomic DNA was extracted from 250 mg of stool using the DNeasy PowerSoil Pro Kit (Qiagen, Hilden, Germany) following the manufacturer's protocol. DNA concentration was quantified using a Qubit 4 Fluorometer (Thermo Fisher Scientific) and quality assessed by agarose gel electrophoresis.

### 16S rRNA Gene Amplicon Sequencing

The V4 region of the 16S rRNA gene was amplified using the 515F/806R primer pair (Caporaso et al., 2012). PCR was performed in triplicate 25 μL reactions containing 12.5 μL KAPA HiFi HotStart ReadyMix, 1 μL of each primer (10 μM), and 2 μL template DNA. Cycling conditions were: 95°C for 3 min; 25 cycles of 95°C for 30 s, 55°C for 30 s, 72°C for 30 s; final extension 72°C for 5 min.

Amplicon libraries were prepared using the Illumina 16S Metagenomic Sequencing Library Preparation protocol and sequenced on an Illumina MiSeq platform (2×250 bp paired-end reads) at the KEMRI sequencing facility.

### Bioinformatics Analysis

Raw sequences were processed using QIIME 2 version 2024.2 (Bolyen et al., 2019). Briefly, reads were demultiplexed, quality filtered, and denoised using DADA2 (Callahan et al., 2016) with default parameters. Taxonomy was assigned using a Naive Bayes classifier trained on the SILVA 138.1 database (Quast et al., 2013). Sequences were aligned using MAFFT (Katoh & Standley, 2013) and a phylogenetic tree constructed using FastTree 2 (Price et al., 2010).

### Statistical Analysis

Alpha diversity metrics (Shannon index, observed features, Faith's phylogenetic diversity) were calculated and compared between groups using Wilcoxon rank-sum tests. Beta diversity was assessed using weighted and unweighted UniFrac distances (Lozupone & Knight, 2005) and visualized using principal coordinates analysis (PCoA). PERMANOVA (Anderson, 2001) was used to test for significant differences in community composition. Differential abundance analysis was performed using ANCOM-BC2 (Lin & Peddada, 2020). All statistical analyses were performed in R version 4.3.2.

## Results

### Participant Characteristics

The urban and rural groups were balanced for age (mean 38.2 vs 39.1 years) and sex (52% vs 48% female). Rural participants consumed significantly more fiber (mean 42 g/day vs 18 g/day, p<0.001) and less processed food (12% vs 58% of caloric intake, p<0.001) based on food frequency questionnaires.

### Sequencing Output

A total of 14.2 million high-quality reads were obtained after quality filtering, with a mean of 118,333 reads per sample (range: 42,156-210,892). After rarefaction to 40,000 reads per sample, 2,847 amplicon sequence variants (ASVs) were identified.

### Alpha Diversity

Rural participants exhibited significantly higher alpha diversity across all metrics examined. Shannon diversity index was 4.2 ± 0.6 in rural versus 3.1 ± 0.8 in urban participants (Wilcoxon p<0.001). Observed ASV richness was 412 ± 89 (rural) versus 287 ± 102 (urban) (p<0.001). Faith's phylogenetic diversity was 28.4 ± 5.1 (rural) versus 19.7 ± 6.3 (urban) (p<0.001).

### Beta Diversity

PCoA of unweighted UniFrac distances revealed clear separation between urban and rural communities (PERMANOVA R²=0.18, p=0.001). The first two principal coordinates explained 32.4% of the total variance.

### Taxonomic Composition

At the phylum level, both groups were dominated by Firmicutes and Bacteroidota, but relative abundances differed significantly. Rural samples had higher Bacteroidota (48% vs 31%) and lower Firmicutes (38% vs 52%) compared to urban samples.

At the genus level, Prevotella was the dominant taxon in rural participants (mean relative abundance 28.3%) but was significantly reduced in urban participants (8.7%, ANCOM-BC2 adjusted p<0.001). Conversely, Bacteroides was enriched in urban participants (22.1% vs 7.4%, adjusted p<0.001).

### Lifestyle-Associated ASVs

ANCOM-BC2 analysis identified 12 ASVs uniquely associated with rural lifestyles (adjusted p<0.05, log fold change >2), including 5 Prevotella ASVs, 3 Treponema ASVs, and 4 Ruminococcaceae ASVs. These taxa have previously been associated with high-fiber diets and traditional lifestyles.

## Discussion

Our findings demonstrate substantial differences in gut microbiome composition between urban and rural Kenyan populations, consistent with patterns observed in other African countries. The higher diversity and Prevotella dominance in rural participants likely reflects their high-fiber, plant-based diets, while the increased Bacteroides in urban participants mirrors trends associated with westernized dietary patterns.

The identification of Treponema in rural participants is noteworthy, as these taxa have been consistently found in traditional populations worldwide but are virtually absent from industrialized populations (Obregon-Tito et al., 2015). Their role in the gut ecosystem remains poorly understood.

### Limitations

This study has several limitations. First, the cross-sectional design precludes causal inference about the relationship between lifestyle factors and microbiome composition. Second, we used 16S rRNA gene sequencing rather than shotgun metagenomics, limiting our ability to characterize functional potential. Third, our sample size may be insufficient to detect subtle associations.

### Data Availability

Raw sequence data have been deposited in the NCBI Sequence Read Archive under BioProject accession PRJNA1234567. Analysis scripts and metadata are available at https://github.com/example/kenya-gut-microbiome.

## References

Anderson MJ. (2001). A new method for non-parametric multivariate analysis of variance. Austral Ecology, 26(1), 32-46.

Bolyen E, et al. (2019). Reproducible, interactive, scalable and extensible microbiome data science using QIIME 2. Nature Biotechnology, 37(8), 852-857.

Callahan BJ, et al. (2016). DADA2: High-resolution sample inference from Illumina amplicon data. Nature Methods, 13(7), 581-583.

Caporaso JG, et al. (2012). Ultra-high-throughput microbial community analysis on the Illumina HiSeq and MiSeq platforms. ISME Journal, 6(8), 1621-1624.

De Filippo C, et al. (2010). Impact of diet in shaping gut microbiota revealed by a comparative study in children from Europe and rural Africa. PNAS, 107(33), 14691-14696.

Lin H & Peddada SD. (2020). Analysis of compositions of microbiomes with bias correction. Nature Communications, 11, 3514.

Lynch SV & Pedersen O. (2016). The human intestinal microbiome in health and disease. NEJM, 375(24), 2369-2379.

Pasolli E, et al. (2019). Extensive unexplored human microbiome diversity revealed by over 150,000 genomes from metagenomes spanning age, geography, and lifestyle. Cell, 176(3), 649-662.

Schnorr SL, et al. (2014). Gut microbiome of the Hadza hunter-gatherers. Nature Communications, 5, 3654.

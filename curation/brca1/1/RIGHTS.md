# BRCA1 source terms and rights review

Redistribution basis: the GDC policies for publication of open-access TCGA
data, with attribution and a prohibition on reidentifying participants.

Reviewed by Codex through an automated source review on October 16, 2026.
This records the assessment below and does not assert a human maintainer's
approval or an independent registry release attestation.

## Official source

The source is the [TCGA Level 3 gene expression archive](https://api.gdc.cancer.gov/data/f0b74706-6b9e-4430-931d-9f233b4ac67c)
linked from the [GDC breast cancer publication page](https://gdc.cancer.gov/about-data/publications/brca_2012).
It contains processed Agilent gene expression measurements produced by the
University of North Carolina Cancer Genomic Characterization Center for TCGA.
The archive was retrieved anonymously, pinned by size and SHA-256, and checked
against its published MD5 checksum. The publication's [open-access GDC
manifest](https://gdc.cancer.gov/system/files/public/file/TCGA-BRCA-2012_Open_GDC-Manifest_0.txt)
lists its UUID, filename, size, and MD5 checksum.

Preparation uses these official measurements and their sample and gene
identifiers. It does not redistribute Iowa's RDS, preparation code, or added
`org.Hs.eg.db` annotations. Iowa's dataset is a comparison reference, so its
repository licensing is not used as the redistribution basis.

## Applicable source policies

The [GDC Data Analysis Policies](https://gdc.cancer.gov/analyze-data/data-analysis-policies)
permit analysis and publication of GDC open-access data, subject to the
prohibition on attempting to reidentify participants.
The [GDC Data Access Policies](https://gdc.cancer.gov/access-data/data-access-policies)
require adherence to the NIH Genomic Data Sharing Policy and acknowledgment
of the datasets and repositories used.
The [TCGA citation guidance](https://www.cancer.gov/ccg/research/genome-sequencing/tcga/using-tcga-data/citing)
requests acknowledgment of the TCGA Research Network and states that the former
publication moratoria have ended.

The assessment here treats publishing this portable numeric extract as
publication of TCGA open-access data under those source policies. This is an
interpretation of the recorded publication terms, not a claim that the policies
name a standard redistribution license or dedicate the data to the public domain.
The manifest records a known source-policy basis with the policy URL and this
automated review.

## Terms to retain

Credit the TCGA Research Network, the University of North Carolina center
that produced the measurements, and the NCI GDC source. Identify the original
archive and the transformations in the dataset documentation. Retain the
prohibition on attempts to reidentify participants.

Use a custom rights statement describing this source-policy basis. No CC0,
CC BY, GPL, Artistic, or repository MIT data license is inferred. Rhee2006's
source-specific rights approach is the model; its Stanford HIVDB public-domain
statement applies to that dataset alone.

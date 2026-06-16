# CareReach Architecture Documentation

## Overview

CareReach is built on Databricks using a modern medallion architecture (Bronze-Silver-Gold) with AI enrichment at multiple stages. This document provides detailed technical specifications for each component.

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Data Flow](#data-flow)
3. [Layer Specifications](#layer-specifications)
4. [AI Components](#ai-components)
5. [Trust Scoring Algorithm](#trust-scoring-algorithm)
6. [Performance Considerations](#performance-considerations)
7. [Security & Permissions](#security--permissions)

---

## System Architecture

### High-Level Components

```
┌─────────────────────────────────────────────────────┐
│                   EXTERNAL DATA SOURCES                       │
├─────────────────────────────────────────────────────┤
│  • data.gov.in (Healthcare Facilities)                      │
│  • India Post (PIN Code Directory)                          │
│  • NFHS-5 (District Health Indicators)                     │
└─────────────────────────────────────────────────────┘
                         │
                         ↓ CSV Upload
                         │
┌─────────────────────────────────────────────────────┐
│                  UNITY CATALOG VOLUME                        │
│            /Volumes/workspace/default/demosai/              │
└─────────────────────────────────────────────────────┘
                         │
                         ↓ PySpark Read
                         │
┌─────────────────────────────────────────────────────┐
│                     BRONZE LAYER                            │
│            (Delta Tables - Raw Data)                        │
├─────────────────────────────────────────────────────┤
│  • bronze_healthcare_facilities                           │
│  • bronze_pin_codes                                        │
│  • bronze_nfhs5_district_indicators                       │
└─────────────────────────────────────────────────────┘
                         │
                         ↓ SQL Transformations
                         │
┌─────────────────────────────────────────────────────┐
│                    SILVER LAYER                             │
│          (Enriched & Cleansed Data)                         │
├─────────────────────────────────────────────────────┤
│  • Geographic Enrichment (PIN code joins)                  │
│  • AI Analysis (DBRX Foundation Model)                     │
│  • Trust Score Computation                                 │
│  • Deduplication & Similarity Detection                    │
│  • Field Coverage Analysis                                 │
└─────────────────────────────────────────────────────┘
                         │
                         ↓ Aggregations
                         │
┌─────────────────────────────────────────────────────┐
│                      GOLD LAYER                             │
│            (Analytics-Ready Tables)                         │
├─────────────────────────────────────────────────────┤
│  • gold_care_gap_analysis                                  │
│  • gold_facility_trust_aggregates                         │
│  • gold_demand_supply_overlay                            │
└─────────────────────────────────────────────────────┘
                         │
          ┌────────────┼────────────┐
          │              │              │
          ↓              ↓              ↓
    ┌─────────┐  ┌─────────┐  ┌─────────┐
    │ MLflow  │  │ Databricks│  │  SQL   │
    │ Agent   │  │   App    │  │Analytics│
    └─────────┘  └─────────┘  └─────────┘
```

---

## Data Flow

### 1. Ingestion Phase

```python
# PySpark reads CSV files from Unity Catalog Volume
df_facilities = spark.read.csv(
    "/Volumes/workspace/default/demosai/healthcare_facilities.csv",
    header=True,
    inferSchema=True
)

# Write to Bronze layer as Delta table
df_facilities.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .saveAsTable("workspace.carereach_bronze.bronze_healthcare_facilities")
```

### 2. Enrichment Phase

**Geographic Enrichment:**

```sql
CREATE OR REPLACE TABLE workspace.carereach_silver.silver_facilities_geo AS
SELECT
  f.*,
  p.officename AS pin_district,
  p.statename AS pin_state,
  p.Taluk AS pin_taluk,
  p.regionname AS pin_region,
  -- Geo validation flags
  CASE
    WHEN UPPER(TRIM(f.district)) = UPPER(TRIM(p.officename)) THEN TRUE
    ELSE FALSE
  END AS district_matches_pin
FROM workspace.carereach_bronze.bronze_healthcare_facilities f
LEFT JOIN workspace.carereach_bronze.bronze_pin_codes p
  ON CAST(f.pincode AS STRING) = CAST(p.pincode AS STRING);
```

**AI Enrichment (Multi-dimensional Extraction):**

```sql
CREATE OR REPLACE TABLE workspace.carereach_silver.silver_facilities_ai AS
SELECT
  *,
  ai_extract(
    facility_description,
    ARRAY(
      'clinical_readiness: INTEGER COMMENT "Estimated clinical capability, 0-100 scale"',
      'accessibility_barriers: STRING COMMENT "Physical or geographic access challenges"',
      'quality_trajectory: STRING COMMENT "Improving, stable, or declining service quality"',
      'workforce_stability: STRING COMMENT "Staff retention and availability patterns"',
      'infrastructure_quality: STRING COMMENT "Physical condition and equipment status"',
      'service_specialization: ARRAY<STRING> COMMENT "Medical specialties available"',
      'data_reliability: INTEGER COMMENT "Confidence in description accuracy, 0-100"'
    )
  ) AS ai_analysis
FROM workspace.carereach_silver.silver_facilities_geo;
```

### 3. Trust Score Computation

**Multi-Factor Trust Scoring:**

```sql
CREATE OR REPLACE TABLE workspace.carereach_silver.silver_facilities_trust AS
SELECT
  *,
  -- Field coverage score (0-1)
  (
    CAST(facility_name IS NOT NULL AS DOUBLE) * 0.10 +
    CAST(facility_type IS NOT NULL AS DOUBLE) * 0.10 +
    CAST(pincode IS NOT NULL AS DOUBLE) * 0.10 +
    CAST(district IS NOT NULL AS DOUBLE) * 0.10 +
    CAST(state IS NOT NULL AS DOUBLE) * 0.10 +
    CAST(telephone IS NOT NULL AS DOUBLE) * 0.05 +
    CAST(facility_description IS NOT NULL AS DOUBLE) * 0.20 +
    CAST(district_matches_pin AS DOUBLE) * 0.15 +
    CAST(ai_analysis IS NOT NULL AS DOUBLE) * 0.10
  ) AS field_coverage_score,
  
  -- AI calibration factor (from model's own reliability assessment)
  COALESCE(ai_analysis.data_reliability / 100.0, 0.5) AS ai_calibration,
  
  -- Final trust score: field coverage * AI calibration
  (
    CAST(facility_name IS NOT NULL AS DOUBLE) * 0.10 +
    CAST(facility_type IS NOT NULL AS DOUBLE) * 0.10 +
    CAST(pincode IS NOT NULL AS DOUBLE) * 0.10 +
    CAST(district IS NOT NULL AS DOUBLE) * 0.10 +
    CAST(state IS NOT NULL AS DOUBLE) * 0.10 +
    CAST(telephone IS NOT NULL AS DOUBLE) * 0.05 +
    CAST(facility_description IS NOT NULL AS DOUBLE) * 0.20 +
    CAST(district_matches_pin AS DOUBLE) * 0.15 +
    CAST(ai_analysis IS NOT NULL AS DOUBLE) * 0.10
  ) * COALESCE(ai_analysis.data_reliability / 100.0, 0.5) AS trust_score
FROM workspace.carereach_silver.silver_facilities_ai;
```

### 4. Aggregation Phase (Gold Layer)

**Care Gap Analysis:**

```sql
CREATE OR REPLACE TABLE workspace.carereach_gold.gold_care_gap_analysis AS
SELECT
  state,
  district,
  COUNT(*) AS facility_count,
  ROUND(AVG(trust_score), 3) AS avg_trust,
  ROUND(AVG(field_coverage_score), 3) AS avg_coverage,
  
  -- Composite gap score (inverse of trust)
  ROUND(1 - AVG(trust_score), 4) AS composite_gap_score,
  
  -- Gap characterization logic
  CASE
    WHEN AVG(trust_score) < 0.30 AND COUNT(*) < 10 
      THEN 'DATA_GAP'
    WHEN AVG(trust_score) >= 0.60 AND COUNT(*) >= 20 
      THEN 'ADEQUATE_COVERAGE'
    WHEN AVG(trust_score) < 0.45 AND COUNT(*) >= 15 
      THEN 'REAL_GAP'
    ELSE 'MIXED_SIGNALS'
  END AS gap_characterization,
  
  -- Intervention priority
  CASE
    WHEN composite_gap_score > 0.75 THEN 'P1_IMMEDIATE'
    WHEN composite_gap_score > 0.60 THEN 'P2_HIGH'
    WHEN composite_gap_score > 0.40 THEN 'P3_MODERATE'
    ELSE 'P4_MONITOR'
  END AS intervention_priority,
  
  -- Confidence level
  CASE
    WHEN AVG(field_coverage_score) >= 0.70 THEN 'HIGH'
    WHEN AVG(field_coverage_score) >= 0.50 THEN 'MEDIUM'
    ELSE 'LOW'
  END AS confidence_level,
  
  -- Phantom facility flag
  CASE
    WHEN AVG(trust_score) < 0.30 AND COUNT(*) < 10 THEN TRUE
    ELSE FALSE
  END AS gap_phantom_facilities,
  
  -- Aggregate lat/long (for mapping)
  ROUND(AVG(latitude), 4) AS latitude,
  ROUND(AVG(longitude), 4) AS longitude
  
FROM workspace.carereach_silver.silver_facilities_trust
WHERE state IS NOT NULL AND district IS NOT NULL
GROUP BY state, district;
```

---

## Layer Specifications

### Bronze Layer

**Purpose**: Raw data ingestion with minimal transformation

**Tables**:

1. `bronze_healthcare_facilities` (10,000 rows, 51 columns)
   - Source: data.gov.in
   - Format: Delta
   - Partitioning: None (small dataset)
   - Schema: Inferred from CSV

2. `bronze_pin_codes` (165,627 rows, 11 columns)
   - Source: India Post
   - Format: Delta
   - Partitioning: By `statename` (36 partitions)
   - Key columns: `pincode`, `officename`, `statename`

3. `bronze_nfhs5_district_indicators` (707 rows, 109 columns)
   - Source: NFHS-5 Survey (2019-21)
   - Format: Delta
   - Partitioning: None
   - Key columns: `district`, `state`, health indicator columns

### Silver Layer

**Purpose**: Enriched, cleansed, and validated data

**Transformations**:

1. **Geographic Enrichment**
   - JOIN with PIN code directory
   - District/state validation
   - Lat/long validation (India bounds: 6-38°N, 67-98°E)

2. **AI Enrichment**
   - Multi-dimensional extraction from descriptions
   - Clinical readiness scoring
   - Quality trajectory assessment
   - Data reliability self-assessment

3. **Trust Scoring**
   - Field coverage computation
   - AI calibration
   - Final trust score (0-1 scale)

4. **Deduplication**
   - Fuzzy name matching (Levenshtein distance)
   - Geographic proximity checks
   - Merge duplicate records

### Gold Layer

**Purpose**: Business-ready aggregates for analytics and AI agent

**Tables**:

1. `gold_care_gap_analysis`
   - Granularity: District/State
   - Key metrics: facility_count, avg_trust, composite_gap_score
   - Derived fields: gap_characterization, intervention_priority, confidence_level
   - Used by: Databricks App (geospatial viz), AI Agent

2. `gold_facility_trust_aggregates`
   - Granularity: Individual facility
   - Enriched with: AI analysis, trust scores, deduplication flags
   - Used by: Data explorer, detailed facility queries

3. `gold_demand_supply_overlay`
   - Granularity: District
   - Combines: Care gap scores + NFHS-5 health indicators
   - Key metrics: demand_intensity, demand_supply_mismatch_index
   - Used by: Prioritization, resource allocation planning

---

## AI Components

### 1. Foundation Model (DBRX Instruct)

**Endpoint**: `databricks-dbrx-instruct`
**Usage**: Text extraction from facility descriptions

**Prompt Template**:

```python
prompt = f"""
Analyze this healthcare facility description and extract structured information:

Description: {facility_description}

Extract the following fields as JSON:
- clinical_readiness (0-100): Estimated clinical capability
- accessibility_barriers (string): Physical/geographic challenges
- quality_trajectory (string): Improving/Stable/Declining
- workforce_stability (string): Staff retention patterns
- infrastructure_quality (string): Physical condition
- service_specialization (array): Medical specialties
- data_reliability (0-100): Confidence in this description's accuracy

Return only valid JSON.
"""
```

**SQL Integration** (using `ai_extract`):

```sql
SELECT
  ai_extract(
    facility_description,
    ARRAY('clinical_readiness: INTEGER', 'accessibility_barriers: STRING', ...)
  ) AS ai_analysis
FROM facilities;
```

### 2. MLflow Agent

**Architecture**:

```yaml
name: carereach-planning-agent
model: databricks-dbrx-instruct
temperature: 0.1
max_tokens: 1000

tools:
  - name: query_gap_analysis
    type: function
    function:
      name: query_gap_analysis
      description: Query district/state-level care gap data
      parameters:
        type: object
        properties:
          state:
            type: string
            description: State name (optional)
          priority:
            type: string
            enum: [P1_IMMEDIATE, P2_HIGH, P3_MODERATE, P4_MONITOR]
            description: Filter by intervention priority
          gap_type:
            type: string
            enum: [REAL_GAP, DATA_GAP, MIXED_SIGNALS, ADEQUATE_COVERAGE]
            description: Filter by gap characterization
        required: []

  - name: query_facilities
    type: function
    function:
      name: query_facilities
      description: Search facilities by location, type, or trust score
      parameters:
        type: object
        properties:
          district:
            type: string
          min_trust:
            type: number
            minimum: 0
            maximum: 1
          max_trust:
            type: number
            minimum: 0
            maximum: 1
        required: []

  - name: query_demand_supply
    type: function
    function:
      name: query_demand_supply
      description: Analyze demand-supply mismatches with NFHS-5 indicators
      parameters:
        type: object
        properties:
          min_mismatch_index:
            type: number
            description: Minimum demand-supply mismatch index
        required: []
```

**Tool Implementation** (Python):

```python
from databricks import sql
import pandas as pd

def query_gap_analysis(state: str = None, priority: str = None, gap_type: str = None) -> pd.DataFrame:
    """
    Query the gold_care_gap_analysis table with filters.
    """
    query = "SELECT * FROM workspace.carereach_gold.gold_care_gap_analysis WHERE 1=1"
    
    if state:
        query += f" AND UPPER(state) = '{state.upper()}'"
    if priority:
        query += f" AND intervention_priority = '{priority}'"
    if gap_type:
        query += f" AND gap_characterization = '{gap_type}'"
    
    query += " ORDER BY composite_gap_score DESC LIMIT 50"
    
    with sql.connect(...) as conn:
        return pd.read_sql(query, conn)
```

---

## Trust Scoring Algorithm

### Formula

```
trust_score = field_coverage_score × ai_calibration_factor

where:
  field_coverage_score = Σ(field_weight × field_present)
  ai_calibration_factor = ai_data_reliability / 100
```

### Field Weights

| Field                     | Weight | Rationale                                      |
|---------------------------|--------|------------------------------------------------|
| facility_name             | 0.10   | Basic identifier                               |
| facility_type             | 0.10   | Category classification                        |
| pincode                   | 0.10   | Geographic validation anchor                   |
| district                  | 0.10   | Administrative geography                       |
| state                     | 0.10   | Top-level geography                            |
| telephone                 | 0.05   | Contact information                            |
| facility_description      | 0.20   | Rich text for AI analysis (highest weight)     |
| district_matches_pin      | 0.15   | Data consistency check                         |
| ai_analysis_present       | 0.10   | AI enrichment successful                       |

**Total**: 1.00

### AI Calibration

The AI model provides a `data_reliability` score (0-100) reflecting its confidence in the extracted information. This serves as a multiplier:

- **High reliability (80-100)**: 0.8-1.0 multiplier
- **Medium reliability (50-79)**: 0.5-0.79 multiplier
- **Low reliability (0-49)**: 0.0-0.49 multiplier

This self-assessment prevents over-confident conclusions from ambiguous or sparse descriptions.

### Example Calculation

**Facility A**:
- All basic fields present: 0.10 + 0.10 + 0.10 + 0.10 + 0.10 + 0.05 = 0.55
- Description present: 0.20
- District matches PIN: 0.15
- AI analysis successful: 0.10
- **Field coverage**: 1.00
- **AI reliability**: 85% = 0.85
- **Final trust score**: 1.00 × 0.85 = **0.85** ✅

**Facility B** (Data Gap Candidate):
- Basic fields: 0.40 (missing some)
- No description: 0.00
- District doesn't match PIN: 0.00
- AI analysis failed: 0.00
- **Field coverage**: 0.40
- **AI reliability**: N/A → default 0.50
- **Final trust score**: 0.40 × 0.50 = **0.20** ❌ (likely phantom)

---

## Performance Considerations

### Query Optimization

1. **Partitioning**:
   - Bronze PIN codes table partitioned by `statename` (36 partitions)
   - Enables partition pruning for state-specific queries

2. **Z-Ordering** (planned):
   ```sql
   OPTIMIZE workspace.carereach_gold.gold_care_gap_analysis
   ZORDER BY (state, composite_gap_score);
   ```

3. **Caching**:
   - Serverless SQL Warehouse result caching (automatic)
   - Databricks App implements in-memory caching for dashboard KPIs

### Data Volume

| Layer  | Table                           | Rows    | Size (Delta) |
|--------|---------------------------------|---------|---------------|
| Bronze | healthcare_facilities           | 10,000  | ~50 MB       |
| Bronze | pin_codes                       | 165,627 | ~20 MB       |
| Bronze | nfhs5_district_indicators       | 707     | ~5 MB        |
| Silver | facilities_enriched             | 9,800   | ~80 MB       |
| Gold   | care_gap_analysis               | 650     | ~2 MB        |
| Gold   | facility_trust_aggregates       | 9,800   | ~85 MB       |
| Gold   | demand_supply_overlay           | 650     | ~10 MB       |

**Total storage**: ~250 MB (Delta format with compression)

### AI Model Latency

- **DBRX Instruct**: ~500ms per facility description
- **Batch processing**: 10,000 facilities in ~1.5 hours (parallel processing)
- **Agent queries**: 200-800ms response time

---

## Security & Permissions

### Unity Catalog Grants

```sql
-- Service principal for Databricks App
CREATE SERVICE PRINCIPAL IF NOT EXISTS `app-carereach`;

-- Grant catalog and schema access
GRANT USAGE ON CATALOG workspace TO `app-carereach`;
GRANT USAGE ON SCHEMA workspace.carereach_gold TO `app-carereach`;
GRANT SELECT ON SCHEMA workspace.carereach_gold TO `app-carereach`;

-- SQL Warehouse access (via UI or SDK)
-- Grant CAN_USE on warehouse 4997437721116114
```

### Model Serving Permissions

```python
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.iam import PermissionLevel

w = WorkspaceClient()

# Grant agent endpoint access to app service principal
w.serving_endpoints.update_permissions(
    serving_endpoint_id="carereach-planning-agent",
    access_control_list=[
        {
            "service_principal_name": "app-carereach",
            "permission_level": PermissionLevel.CAN_QUERY
        }
    ]
)
```

### OAuth M2M Authentication

**Databricks App Configuration** (`app.yaml`):

```yaml
name: carereach
resources:
  - name: carereach-planning-agent
    type: serving-endpoint
    permission: CAN_QUERY
  - name: carereach-warehouse
    type: sql-warehouse
    permission: CAN_USE
  - name: workspace.carereach_gold
    type: schema
    permission: SELECT
```

**Runtime Authentication** (automatic):

```python
import os
from databricks import sql

# OAuth credentials injected by Databricks Apps runtime
conn = sql.connect(
    server_hostname=os.environ["DATABRICKS_HOST"],
    http_path=f"/sql/1.0/warehouses/{os.environ['SQL_WAREHOUSE_ID']}",
    credentials_provider=lambda: (
        os.environ["DATABRICKS_CLIENT_ID"],
        os.environ["DATABRICKS_CLIENT_SECRET"],
    ),
)
```

---

## Appendix: SQL Schema Reference

### Gold Layer - Full Schema

**gold_care_gap_analysis**:

```sql
CREATE TABLE workspace.carereach_gold.gold_care_gap_analysis (
  state STRING,
  district STRING,
  facility_count BIGINT,
  avg_trust DOUBLE,
  avg_coverage DOUBLE,
  composite_gap_score DOUBLE,
  gap_characterization STRING,  -- REAL_GAP | DATA_GAP | MIXED_SIGNALS | ADEQUATE_COVERAGE
  intervention_priority STRING, -- P1_IMMEDIATE | P2_HIGH | P3_MODERATE | P4_MONITOR
  confidence_level STRING,      -- HIGH | MEDIUM | LOW
  gap_phantom_facilities BOOLEAN,
  latitude DOUBLE,
  longitude DOUBLE
)
USING DELTA
LOCATION 's3://...';
```

**gold_facility_trust_aggregates**:

```sql
CREATE TABLE workspace.carereach_gold.gold_facility_trust_aggregates (
  facility_id STRING,
  facility_name STRING,
  facility_type STRING,
  state STRING,
  district STRING,
  pincode STRING,
  latitude DOUBLE,
  longitude DOUBLE,
  
  -- AI enrichment fields
  ai_clinical_readiness INT,
  ai_accessibility_barriers STRING,
  ai_quality_trajectory STRING,
  ai_workforce_stability STRING,
  ai_infrastructure_quality STRING,
  ai_service_specialization ARRAY<STRING>,
  ai_data_reliability INT,
  
  -- Trust scores
  field_coverage_score DOUBLE,
  ai_calibration DOUBLE,
  trust_score DOUBLE,
  
  -- Deduplication
  is_duplicate BOOLEAN,
  canonical_facility_id STRING,
  similarity_score DOUBLE
)
USING DELTA;
```

---

## Conclusion

This architecture leverages Databricks' unified data + AI platform to build a scalable, maintainable, and performant healthcare analytics system. The medallion architecture ensures data quality progresses through each layer, while AI enrichment adds critical insights for trust-weighted decision making.

For implementation details, see [SETUP.md](SETUP.md).
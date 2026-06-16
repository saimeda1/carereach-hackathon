# CareReach Setup Guide

This guide will walk you through setting up the complete CareReach healthcare analytics system on Databricks.

## Prerequisites

### Databricks Workspace Requirements

- **Databricks Workspace**: AWS, Azure, or GCP (this guide uses AWS)
- **Unity Catalog**: Enabled and configured
- **Serverless SQL Warehouse**: Access to create or use existing
- **Model Serving**: Permissions to create and deploy models
- **Databricks Apps**: Enabled in your workspace
- **Foundation Model API**: Access to DBRX Instruct or similar

### User Permissions Required

- `CREATE CATALOG` or access to existing catalog
- `CREATE SCHEMA` within the catalog
- `CREATE TABLE` within schemas
- Ability to deploy Model Serving endpoints
- Ability to deploy Databricks Apps
- Access to Unity Catalog Volumes

### Local Development (Optional)

- Python 3.10+
- Databricks CLI installed
- Git

---

## Step 1: Clone the Repository

### Option A: Using Databricks Repos (Recommended)

1. Navigate to your Databricks workspace
2. Go to **Repos** in the left sidebar
3. Click **Add Repo**
4. Enter the GitHub URL: `https://github.com/YOUR_USERNAME/carereach-hackathon`
5. Select the target folder: `/Users/YOUR_EMAIL/carereach-hackathon`
6. Click **Create Repo**

### Option B: Using Databricks CLI

```bash
databricks repos create \
  --url https://github.com/YOUR_USERNAME/carereach-hackathon \
  --provider github \
  --path /Users/YOUR_EMAIL/carereach-hackathon
```

---

## Step 2: Set Up Unity Catalog Structure

### 2.1 Create Catalog and Schemas

Run these SQL commands in a Databricks SQL Editor or notebook:

```sql
-- Create catalog (or use existing)
CREATE CATALOG IF NOT EXISTS workspace;

-- Create schemas for medallion architecture
CREATE SCHEMA IF NOT EXISTS workspace.carereach_bronze
  COMMENT 'Raw ingestion layer for healthcare data';

CREATE SCHEMA IF NOT EXISTS workspace.carereach_silver
  COMMENT 'Cleansed and enriched healthcare data';

CREATE SCHEMA IF NOT EXISTS workspace.carereach_gold
  COMMENT 'Analytics-ready healthcare aggregates';

-- Verify creation
SHOW SCHEMAS IN workspace LIKE 'carereach%';
```

### 2.2 Create Unity Catalog Volume

```sql
-- Create volume for data files
CREATE VOLUME IF NOT EXISTS workspace.default.demosai;

-- Verify
SHOW VOLUMES IN workspace.default;
```

---

## Step 3: Upload Data Files

### 3.1 Download Data Sources

1. **Healthcare Facilities**:
   - Source: [data.gov.in Healthcare Facilities](https://data.gov.in)
   - File: `healthcare_facilities.csv`
   - Expected columns: 51 (facility_name, facility_type, description, pincode, district, state, etc.)

2. **India Post PIN Code Directory**:
   - Source: [data.gov.in PIN Codes](https://data.gov.in/resource/all-india-pincode-directory)
   - File: `india_pin_codes.csv`
   - Expected columns: pincode, officename, statename, Taluk, regionname, etc.

3. **NFHS-5 District Indicators**:
   - Source: [NFHS-5 Data Repository](http://rchiips.org/nfhs/)
   - File: `nfhs5_district_indicators.csv`
   - Expected columns: district, state, stunting_under5_pct, immunization metrics, etc.

### 3.2 Upload to Unity Catalog Volume

**Option A: Using Databricks UI**

1. Navigate to **Catalog** in the left sidebar
2. Expand: `workspace` → `default` → `demosai`
3. Click **Upload** button
4. Select all three CSV files
5. Wait for upload to complete

**Option B: Using Databricks CLI**

```bash
# Upload files to volume
databricks fs cp healthcare_facilities.csv \
  dbfs:/Volumes/workspace/default/demosai/healthcare_facilities.csv

databricks fs cp india_pin_codes.csv \
  dbfs:/Volumes/workspace/default/demosai/india_pin_codes.csv

databricks fs cp nfhs5_district_indicators.csv \
  dbfs:/Volumes/workspace/default/demosai/nfhs5_district_indicators.csv

# Verify
databricks fs ls dbfs:/Volumes/workspace/default/demosai/
```

---

## Step 4: Run the Data Pipeline

### 4.1 Open the Main Notebook

Navigate to the notebook:
```
/Users/YOUR_EMAIL/carereach-hackathon/notebooks/Healthcare_Facility_Trust_Weighted_Analysis.ipynb
```

### 4.2 Configure Settings

In Cell 4 (Configuration), update these variables if needed:

```python
# Catalog & Schema Settings
CATALOG = "workspace"
SCHEMA_BRONZE = "carereach_bronze"
SCHEMA_SILVER = "carereach_silver"
SCHEMA_GOLD = "carereach_gold"

# Data source path
VOLUME_PATH = "/Volumes/workspace/default/demosai/"
```

### 4.3 Execute Pipeline Cells

Run cells in order:

1. **Cell 5-6**: Load data from volume into Bronze tables (~2 minutes)
2. **Cell 7-8**: Create Bronze layer schemas
3. **Cell 9-11**: Silver layer enrichment with AI (~30 minutes for 10K facilities)
4. **Cell 12-15**: Gold layer aggregations (~5 minutes)
5. **Cell 16-20**: Verify data quality

**Expected Output**:
```
Bronze tables created: 3
  - bronze_healthcare_facilities: 10,000 rows
  - bronze_pin_codes: 165,627 rows
  - bronze_nfhs5_district_indicators: 707 rows

Silver tables created: 1
  - silver_facilities_trust: 9,800 rows (200 deduplicated)

Gold tables created: 3
  - gold_care_gap_analysis: 650 districts
  - gold_facility_trust_aggregates: 9,800 facilities
  - gold_demand_supply_overlay: 650 districts
```

---

## Step 5: Deploy the AI Agent

### 5.1 Configure Agent

Create `agent/agent_config.yaml`:

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
      description: "Query district/state-level care gap data with filters"
      parameters:
        type: object
        properties:
          state:
            type: string
            description: "State name to filter (optional)"
          priority:
            type: string
            enum: ["P1_IMMEDIATE", "P2_HIGH", "P3_MODERATE", "P4_MONITOR"]
            description: "Intervention priority level"
          gap_type:
            type: string
            enum: ["REAL_GAP", "DATA_GAP", "MIXED_SIGNALS", "ADEQUATE_COVERAGE"]
            description: "Gap characterization type"
        required: []
```

### 5.2 Deploy Agent with MLflow

Run in a notebook cell:

```python
import mlflow
from databricks import agents

# Set MLflow experiment
mlflow.set_experiment("/Users/YOUR_EMAIL/carereach-agent")

# Deploy agent
agent_info = agents.deploy(
    name="carereach-planning-agent",
    config="./agent/agent_config.yaml",
    description="AI agent for healthcare access gap analysis and planning"
)

print(f"Agent deployed: {agent_info.name}")
print(f"Endpoint URL: {agent_info.endpoint_url}")
```

### 5.3 Test Agent

```python
from mlflow.deployments import get_deploy_client

client = get_deploy_client("databricks")

response = client.predict(
    endpoint="carereach-planning-agent",
    inputs={
        "messages": [
            {"role": "user", "content": "Which districts have P1_IMMEDIATE priority gaps?"}
        ]
    }
)

print(response["choices"][0]["message"]["content"])
```

---

## Step 6: Deploy the Databricks App

### 6.1 Configure App Files

Navigate to the `app/` directory and verify these files:

1. **app.py**: Main Gradio application
2. **app.yaml**: Databricks app configuration
3. **requirements.txt**: Python dependencies

**app.yaml**:

```yaml
name: carereach

env:
  - name: DATABRICKS_HOST
    valueFrom:
      host: workspace
  - name: SQL_WAREHOUSE_ID
    value: "YOUR_WAREHOUSE_ID"  # ← Update this
  - name: ENDPOINT_NAME
    value: "carereach-planning-agent"

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

### 6.2 Deploy App

```bash
# From workspace terminal or notebook
databricks apps deploy carereach \
  --source-code-path /Workspace/Users/YOUR_EMAIL/carereach-hackathon/app

# This will output the app URL:
# App deployed successfully!
# URL: https://carereach-XXXXXXX.aws.databricksapps.com
```

### 6.3 Grant Permissions

The app requires permissions that cannot be auto-granted. Follow these steps:

#### A. SQL Warehouse Permission

1. Go to **SQL Warehouses** in Databricks UI
2. Click on your warehouse (ID from app.yaml)
3. Click **Permissions** tab
4. Click **Grant** → **Service Principal**
5. Search for: `app-XXXXXX carereach` (shown in deployment output)
6. Select **CAN USE**
7. Click **Save**

#### B. Unity Catalog Permissions

Run in SQL Editor:

```sql
-- Replace with your app's service principal name
SET VAR.sp_name = 'app-226vqk carereach';

GRANT USAGE ON CATALOG workspace TO IDENTIFIER(VAR.sp_name);
GRANT USAGE ON SCHEMA workspace.carereach_gold TO IDENTIFIER(VAR.sp_name);
GRANT SELECT ON SCHEMA workspace.carereach_gold TO IDENTIFIER(VAR.sp_name);

-- Verify
SHOW GRANTS ON SCHEMA workspace.carereach_gold;
```

#### C. Model Serving Endpoint Permission

1. Go to **Machine Learning** → **Serving**
2. Click **carereach-planning-agent**
3. Click **Permissions** tab
4. Click **Grant** → **Service Principal**
5. Search for: `app-XXXXXX carereach`
6. Select **CAN QUERY**
7. Click **Save**

### 6.4 Wait for Propagation

Permissions take 1-2 minutes to propagate. Then:

1. Open the app URL in your browser
2. Test each tab:
   - **Dashboard**: Should show KPIs and map
   - **Analytics**: Should display charts
   - **AI Agent**: Test a query
   - **Live Metrics**: Should show facility data

---

## Step 7: Verify Installation

### 7.1 Data Quality Checks

Run in SQL Editor:

```sql
-- Check record counts
SELECT 'Bronze Facilities' AS layer, COUNT(*) AS count 
  FROM workspace.carereach_bronze.bronze_healthcare_facilities
UNION ALL
SELECT 'Silver Trust Scores', COUNT(*) 
  FROM workspace.carereach_silver.silver_facilities_trust
UNION ALL
SELECT 'Gold Gap Analysis', COUNT(*) 
  FROM workspace.carereach_gold.gold_care_gap_analysis;

-- Verify trust score distribution
SELECT
  CASE
    WHEN trust_score >= 0.8 THEN 'Excellent (0.8-1.0)'
    WHEN trust_score >= 0.6 THEN 'Good (0.6-0.8)'
    WHEN trust_score >= 0.4 THEN 'Fair (0.4-0.6)'
    ELSE 'Poor (0.0-0.4)'
  END AS trust_category,
  COUNT(*) AS facility_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM workspace.carereach_silver.silver_facilities_trust
GROUP BY 1
ORDER BY MIN(trust_score) DESC;

-- Check gap characterization distribution
SELECT
  gap_characterization,
  COUNT(*) AS district_count,
  ROUND(AVG(facility_count), 1) AS avg_facilities,
  ROUND(AVG(avg_trust), 3) AS avg_trust_score
FROM workspace.carereach_gold.gold_care_gap_analysis
GROUP BY gap_characterization
ORDER BY COUNT(*) DESC;
```

### 7.2 Agent Functionality Test

```python
from mlflow.deployments import get_deploy_client

client = get_deploy_client("databricks")

# Test queries
test_queries = [
    "Which districts have P1_IMMEDIATE priority?",
    "Show me DATA_GAP regions (likely phantom facilities)",
    "What's the average trust score by state?",
    "Find districts with high demand but low facility coverage"
]

for query in test_queries:
    print(f"\nQuery: {query}")
    response = client.predict(
        endpoint="carereach-planning-agent",
        inputs={"messages": [{"role": "user", "content": query}]}
    )
    print(f"Response: {response['choices'][0]['message']['content'][:200]}...")
```

### 7.3 App Functionality Test

1. Navigate to the app URL
2. **Dashboard Tab**:
   - Verify KPI cards show numbers
   - Check India map renders
   - Hover over states for tooltips
3. **Analytics Tab**:
   - Verify charts load
   - Test filters
4. **AI Agent Tab**:
   - Type: "Show P1 priority districts"
   - Verify response appears
5. **Live Metrics Tab**:
   - Check facility table populates
   - Test search/filter

---

## Troubleshooting

### Issue: "Table not found" errors

**Solution**:
```sql
-- Verify tables exist
SHOW TABLES IN workspace.carereach_bronze;
SHOW TABLES IN workspace.carereach_silver;
SHOW TABLES IN workspace.carereach_gold;

-- If missing, re-run pipeline notebook cells
```

### Issue: "Permission denied" in app

**Solution**:
1. Check service principal name:
   ```bash
   databricks apps get carereach
   ```
2. Verify grants:
   ```sql
   SHOW GRANTS ON SCHEMA workspace.carereach_gold;
   ```
3. Re-grant if missing:
   ```sql
   GRANT SELECT ON SCHEMA workspace.carereach_gold TO `app-XXXXXX carereach`;
   ```

### Issue: AI enrichment fails

**Solution**:
1. Verify Foundation Model API access:
   ```python
   from databricks.sdk import WorkspaceClient
   w = WorkspaceClient()
   
   # List available models
   models = w.serving_endpoints.list()
   print([m.name for m in models if 'dbrx' in m.name.lower()])
   ```
2. Check if you hit rate limits (wait and retry)
3. Consider batching smaller (100 facilities at a time)

### Issue: Agent returns "No data found"

**Solution**:
1. Verify gold tables populated:
   ```sql
   SELECT COUNT(*) FROM workspace.carereach_gold.gold_care_gap_analysis;
   ```
2. Check agent endpoint status:
   ```bash
   databricks serving-endpoints get carereach-planning-agent
   ```
3. Review agent logs:
   ```bash
   databricks serving-endpoints logs carereach-planning-agent
   ```

### Issue: App not loading/timeout

**Solution**:
1. Check app status:
   ```bash
   databricks apps get carereach
   ```
2. View app logs:
   ```bash
   databricks apps logs carereach
   ```
3. Redeploy if needed:
   ```bash
   databricks apps deploy carereach \
     --source-code-path /Workspace/Users/YOUR_EMAIL/carereach-hackathon/app
   ```

---

## Performance Tuning

### 1. Optimize Gold Tables

```sql
-- Enable Predictive Optimization (recommended)
ALTER TABLE workspace.carereach_gold.gold_care_gap_analysis
  SET TBLPROPERTIES('delta.autoOptimize.optimizeWrite' = 'true');

-- Z-Order for faster state/priority queries
OPTIMIZE workspace.carereach_gold.gold_care_gap_analysis
  ZORDER BY (state, intervention_priority);

-- Vacuum old versions (after testing)
VACUUM workspace.carereach_gold.gold_care_gap_analysis RETAIN 7 HOURS;
```

### 2. Scale SQL Warehouse

For production workloads:

1. Go to **SQL Warehouses**
2. Edit your warehouse
3. Change cluster size: **Small** → **Medium** or **Large**
4. Enable **Serverless** for best performance

### 3. Agent Caching

Enable result caching for repeated queries:

```python
# In agent deployment
agents.deploy(
    name="carereach-planning-agent",
    config="./agent/agent_config.yaml",
    enable_caching=True,  # ← Add this
    cache_ttl=3600  # 1 hour
)
```

---

## Next Steps

1. **Customize Analysis**: Modify trust score weights for your use case
2. **Add Data Sources**: Integrate additional health indicators
3. **Automate Refresh**: Set up scheduled jobs for daily updates
4. **Create Dashboards**: Build Lakeview dashboards for leadership
5. **Expand Geography**: Add more countries/regions
6. **Mobile App**: Deploy a mobile interface for field workers

---

## Support

For issues or questions:

1. **Check Documentation**:
   - [README.md](README.md)
   - [ARCHITECTURE.md](ARCHITECTURE.md)
   - [Databricks Docs](https://docs.databricks.com)

2. **GitHub Issues**:
   - Open an issue: https://github.com/YOUR_USERNAME/carereach-hackathon/issues

3. **Community**:
   - Databricks Community: https://community.databricks.com

---

## Appendix: Sample Data Format

### Healthcare Facilities CSV

```csv
facility_name,facility_type,facility_description,pincode,district,state,latitude,longitude,...
"District Hospital","Government","Multi-specialty hospital with 200 beds...",560001,"Bangalore","Karnataka",12.9716,77.5946,...
```

### PIN Codes CSV

```csv
pincode,officename,statename,Taluk,regionname,...
560001,"Bangalore GPO","Karnataka","Bangalore","Bangalore",...
```

### NFHS-5 CSV

```csv
district,state,stunting_under5_pct,anaemia_children_pct,full_immunization_pct,infant_mortality_rate,...
"Bangalore","Karnataka",24.5,58.3,76.4,24,...
```

---

**Setup Complete! 🎉**

Your CareReach healthcare analytics system is now fully operational.
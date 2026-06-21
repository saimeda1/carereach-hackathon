# CareReach: AI-Powered Healthcare Access Planning for India

[![Databricks](https://img.shields.io/badge/Databricks-Apps%20%26%20Agents-FF3621?logo=databricks)](https://databricks.com)
[![Hackathon](https://img.shields.io/badge/Hackathon-DAIS%20for%20Good%202026-blue)](https://databricks.com)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

> **🏆 Submission for Databricks Apps & Agents Hackathon

### Demo Video

🎥 **[Watch Demo Video](https://youtu.be/Qqc8unLr3sY)** 

## 🎯 Overview

**CareReach** is an AI-powered healthcare access planning system designed to help health administrators in India distinguish **real healthcare gaps** from **data-poor regions** using trust-weighted evidence aggregation. Built entirely on the Databricks platform, it combines advanced data engineering, AI enrichment, and an intelligent planning agent to provide actionable insights for healthcare resource allocation.

### The Challenge

Healthcare planners in India must allocate limited resources across:
- **10,000+ healthcare facilities**
- **707 districts** across 36 states
- **51 data fields** per facility (structured & semi-structured)
- Highly variable data quality and completeness

### Current Pain Points

1. **Data Quality Ambiguity**: Can't distinguish real gaps from reporting gaps
2. **Fragmented Information**: Data scattered across multiple government sources
3. **Manual Analysis**: No automated way to assess facility trustworthiness
4. **Delayed Decisions**: Weeks of manual review before intervention planning
5. **Resource Waste**: Millions spent investigating phantom gaps

## 💡 The Solution

### CareReach Platform Components

#### 1. **Trust-Weighted Evidence Pipeline**
- Ingests 10,000+ facility records from government open data
- Uses **AI enrichment** (Databricks Foundation Models) to extract:
  - Clinical readiness indicators
  - Accessibility barriers
  - Quality trajectory
  - Workforce stability
- Computes **trust scores** (0-1) calibrated by AI's own data-reliability assessment
- Aggregates evidence at district/state levels

#### 2. **Intelligent Planning Agent**
- Built with **Databricks Agent Framework** and **MLflow**
- Queries the gold-layer tables via natural language
- Provides:
  - Gap characterization (REAL_GAP vs DATA_GAP)
  - Intervention priority levels (P1_IMMEDIATE → P4_MONITOR)
  - Confidence assessments (HIGH, MEDIUM, LOW)
  - Actionable recommendations

#### 3. **Interactive Databricks App**
- Modern **Gradio** web interface deployed as a Databricks App
- Features:
  - 📊 **Real-time KPI Dashboard**: Gap regions, priority counts, trust metrics
  - 🗺️ **Geospatial Visualization**: State choropleth + district bubble map
  - 📈 **Advanced Analytics**: Gap distribution, demand-supply overlay
  - 💬 **AI Chat Interface**: Natural language queries to the planning agent
  - 📋 **Data Explorer**: Drill down into facility-level details

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                  │
├─────────────────────────────────────────────────────────────────────┤
│ • Healthcare Facilities (10K records, 51 cols)                      │
│ • India Post PIN Code Directory (165K records)                      │
│ • NFHS-5 District Health Indicators (707 districts, 109 metrics)    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     BRONZE LAYER (Raw Data)                          │
├─────────────────────────────────────────────────────────────────────┤
│ • bronze_healthcare_facilities                                       │
│ • bronze_pin_codes                                                   │
│ • bronze_nfhs5_district_indicators                                   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                  SILVER LAYER (Enrichment)                           │
├─────────────────────────────────────────────────────────────────────┤
│ • Geographic enrichment (PIN code joins)                             │
│ • AI-powered description analysis (Foundation Models)                │
│ • Trust score computation                                            │
│ • Deduplication & similarity detection                               │
│ • Field coverage analysis                                            │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    GOLD LAYER (Analytics)                            │
├─────────────────────────────────────────────────────────────────────┤
│ • gold_care_gap_analysis (district/state aggregates)                │
│ • gold_facility_trust_aggregates (enriched facility data)            │
│ • gold_demand_supply_overlay (NFHS-5 health indicators)             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   CONSUMPTION LAYER                                  │
├─────────────────────────────────────────────────────────────────────┤
│ • MLflow AI Agent (carereach-planning-agent)                        │
│ • Databricks App (Gradio web interface)                             │
│ • SQL Analytics & Dashboards                                         │
└─────────────────────────────────────────────────────────────────────┘
```

## ✨ Key Features

### 1. **Trust-Weighted Evidence Aggregation**
- **Field Coverage Scoring**: Weights based on data completeness
- **AI Calibration**: Uses model's own reliability assessment
- **Multi-dimensional Trust**: Infrastructure, service quality, accessibility, workforce

### 2. **Intelligent Gap Characterization**
- **REAL_GAP**: High facility count but poor trust/quality
- **DATA_GAP**: Low facility count AND low trust (likely phantom)
- **MIXED_SIGNALS**: Ambiguous patterns requiring investigation
- **ADEQUATE_COVERAGE**: Well-served regions

### 3. **Priority-Based Intervention Planning**
- **P1_IMMEDIATE**: Critical gaps requiring urgent action
- **P2_HIGH**: Significant gaps for near-term planning
- **P3_MODERATE**: Medium-term improvement opportunities
- **P4_MONITOR**: Watch areas for emerging issues

### 4. **Confidence Assessment**
- **HIGH**: Strong evidence, clear patterns
- **MEDIUM**: Moderate evidence, some ambiguity
- **LOW**: Limited evidence, requires field verification

### 5. **Geospatial Intelligence**
- State-level choropleth maps
- District-level bubble visualizations
- Demand-supply overlay analysis
- Interactive filtering and drill-down


## 🔧 Technical Implementation

### Technology Stack

- **Platform**: Databricks (AWS)
- **Compute**: Serverless SQL Warehouses
- **Storage**: Delta Lake (Unity Catalog)
- **AI/ML**: 
  - Databricks Foundation Model API (DBRX Instruct)
  - MLflow Agent Framework
  - Databricks Model Serving
- **App Framework**: Gradio
- **Data Processing**: PySpark, Databricks SQL
- **Visualization**: Plotly, Folium
- **Orchestration**: Databricks Notebooks

### Data Sources

1. **Healthcare Facilities Dataset**
   - Source: data.gov.in (Government of India Open Data)
   - Records: ~10,000 facilities
   - Fields: 51 columns (structured + semi-structured descriptions)

2. **India Post PIN Code Directory**
   - Source: data.gov.in
   - Records: 165,627 PIN codes
   - Purpose: Geographic enrichment and validation

3. **NFHS-5 District Health Indicators**
   - Source: National Family Health Survey (2019-21)
   - Coverage: 707 districts
   - Metrics: 109 health indicators (stunting, immunization, anemia, etc.)



### Agent Capabilities

1. **Gap Analysis Queries**
   - "Which districts have the highest priority gaps?"
   - "Show me DATA_GAP regions that might be phantom facilities"
   - "What's the trust distribution across states?"

2. **Facility Search**
   - "Find all primary health centers in Maharashtra with trust < 0.4"
   - "Show facilities with high accessibility barriers"

3. **Demand-Supply Analysis**
   - "Which districts have high stunting rates but low facility coverage?"
   - "Where is the mismatch between health demand and supply worst?"

4. **Intervention Planning**
   - "Recommend immediate interventions for Uttar Pradesh"
   - "What's the evidence confidence level for priority gaps?"


### Example Agent Queries

```
"Which districts have P1_IMMEDIATE priority gaps?"

"Show me states with the lowest average trust scores"

"Find districts with high demand intensity but low facility coverage"

"What are the top 5 districts for immediate healthcare intervention?"

"Explain the difference between REAL_GAP and DATA_GAP"
```



### Technologies

- **Databricks** for the unified data + AI platform
- **MLflow** for agent framework and model serving
- **Gradio** for rapid app prototyping
- **Plotly** for interactive visualizations


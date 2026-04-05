# K-Dense: AI Co-Scientist Platform

## What is K-Dense?

K-Dense is an AI-powered research platform that functions as an "AI co-scientist" capable of autonomously executing complex scientific tasks across multiple domains. It combines large language models with specialized scientific skills, databases, and computational tools to provide a comprehensive research workspace.

The platform exists in three main forms:
1. **K-Dense Web** - Hosted subscription platform with full features
2. **K-Dense BYOK** - Free, open-source desktop version (Bring Your Own Keys)
3. **Claude Scientific Skills** - Open-source skill collection that powers the platform

K-Dense is designed for scientists, researchers, analysts, and curious individuals who need to process complex scientific data, run analyses, and generate research outputs without being locked into a single AI provider.

## How It Works

### Core Architecture

K-Dense operates on several key components:

1. **AI Agent System**: Main "Kady" agent that delegates to specialized AI experts
2. **Scientific Skills**: 170+ specialized skills covering 22 scientific disciplines
3. **Database Integrations**: Direct access to 250+ scientific databases
4. **Tool Generation**: Dynamic creation of tools from 500,000+ Python packages
5. **File Processing**: Native support for 200+ scientific data formats
6. **Workflow Engine**: 326 ready-to-use scientific workflows

### Technical Process

1. **Task Analysis**: User input is analyzed and delegated to appropriate AI experts
2. **Skill Selection**: Relevant scientific skills are chosen based on the task domain
3. **Tool Generation**: Required Python functions are converted into callable tools
4. **Database Queries**: Scientific databases are accessed for relevant data
5. **Code Execution**: Analysis code is written and executed in isolated environments
6. **Output Generation**: Results are formatted as papers, presentations, or reports

### AI Expert System

K-Dense uses a multi-agent architecture where:
- **Main Agent (Kady)**: Handles user interaction and task delegation
- **Specialized Experts**: AI agents focused on specific domains (bioinformatics, chemistry, finance, etc.)
- **Skill Integration**: Each expert has access to domain-specific scientific skills
- **Model Flexibility**: Supports 40+ AI models from different providers

## Platform Versions and Features

### K-Dense BYOK (Free Open-Source Version)

**Available Features:**
- Desktop application running locally
- "Kady" AI assistant with expert delegation
- 170+ scientific skills from Claude Scientific Skills
- 40+ AI model support (OpenAI, Anthropic, Google, xAI, Qwen, etc.)
- Web search capabilities
- Local file handling and sandboxing
- 250+ scientific database access
- 326 ready-to-use workflows
- Custom MCP server integration
- Optional Modal cloud compute for heavy workloads
- Data privacy (everything stays local)

**Requirements:**
- WSL (Windows Subsystem for Linux)
- API keys from OpenRouter.ai
- Optional: Parallel.ai and Modal.com accounts

**Limitations:**
- Manual setup and configuration
- Local computation only (unless using Modal)
- Community support only
- Beta status (active development)

### K-Dense Web (Subscription Platform)

**Additional Features:**
- Cloud-based hosting with no setup required
- 200+ scientific skills (vs 170+ in BYOK)
- Cloud GPU access for heavy computations
- Priority support and SLA guarantees
- Advanced collaboration features
- Automatic updates and maintenance
- Enhanced security features
- Professional templates and outputs
- Advanced workflow orchestration
- Team management capabilities
- Backup and disaster recovery
- Integration with institutional systems

**Pricing:**
- Free tier available with basic features
- Paid tiers for advanced features and compute
- No credit card required for free tier

### Claude Scientific Skills (Open Source Skills)

**What's Included:**
- 170+ individual scientific skills
- Domain-specific expertise across 22 disciplines
- Curated documentation and examples
- Integration with scientific Python packages
- Regular updates and community contributions

**Skill Categories:**
- 🧬 Bioinformatics & Genomics
- 🧪 Cheminformatics & Drug Discovery
- 🔬 Proteomics & Mass Spectrometry
- 🏥 Clinical Research & Precision Medicine
- 🧠 Healthcare AI & Clinical ML
- 🖼️ Medical Imaging & Digital Pathology
- 🤖 Machine Learning & AI
- 🔮 Materials Science & Chemistry
- 🌌 Physics & Astronomy
- ⚙️ Engineering & Simulation
- 📊 Data Analysis & Visualization
- 🌍 Geospatial Science & Remote Sensing
- 🧪 Laboratory Automation
- 📚 Scientific Communication
- 🔬 Multi-omics & Systems Biology
- 🧬 Protein Engineering & Design
- 🎓 Research Methodology

**Repository Links:**
- **Main Repository**: https://github.com/K-Dense-AI/claude-scientific-skills
- **Documentation**: https://github.com/K-Dense-AI/claude-scientific-skills/blob/main/docs/
- **Examples**: https://github.com/K-Dense-AI/claude-scientific-skills/blob/main/docs/examples.md
- **Skills List**: https://github.com/K-Dense-AI/claude-scientific-skills/blob/main/docs/scientific-skills.md
- **Releases**: https://github.com/K-Dense-AI/claude-scientific-skills/releases

## Using the Open Source Skills Repository

### Quick Start Guide

#### 1. Clone the Repository

```bash
# Clone the main skills repository
git clone https://github.com/K-Dense-AI/claude-scientific-skills.git
cd claude-scientific-skills

# Explore the structure
ls -la
# You'll see directories like:
# - skills/          # Individual skill files
# - docs/           # Documentation and examples
# - workflows/       # Predefined workflows
# - examples/       # Usage examples
```

#### 2. Understand the Directory Structure

```
claude-scientific-skills/
├── skills/
│   ├── bioinformatics/
│   │   ├── sequence-analysis.md
│   │   ├── blast-search.md
│   │   └── phylogenetics.md
│   ├── cheminformatics/
│   │   ├── molecular-properties.md
│   │   ├── virtual-screening.md
│   │   └── docking.md
│   ├── machine-learning/
│   │   ├── time-series-analysis.md
│   │   ├── deep-learning.md
│   │   └── model-interpretability.md
│   └── ... (other domains)
├── docs/
│   ├── examples.md          # Comprehensive examples
│   ├── scientific-skills.md  # Complete skills list
│   ├── installation.md       # Setup instructions
│   └── troubleshooting.md   # Common issues
├── workflows/
│   ├── drug-discovery-pipeline.md
│   ├── genomics-analysis.md
│   └── clinical-research.md
└── examples/
    ├── notebooks/
    ├── scripts/
    └── data/
```

#### 3. Install Dependencies

```bash
# Check the requirements file
cat requirements.txt

# Install core scientific packages
pip install biopython rdkit-pypi scanpy scikit-learn
pip install pandas numpy matplotlib seaborn
pip install torch torchvision
pip install requests beautifulsoup4

# For specific domains, you might need additional packages:
# Bioinformatics: pysam pyfastx
# Chemistry: openbabel pymol
# Physics: astropy sympy
# Geospatial: geopandas rasterio
```

#### 4. Browse Available Skills

**Online Browsing:**
- Visit https://github.com/K-Dense-AI/claude-scientific-skills/blob/main/docs/scientific-skills.md
- Skills are organized by domain with descriptions
- Each skill links to its detailed documentation

**Local Browsing:**
```bash
# List all skill categories
find skills/ -type d | head -20

# View skills in a specific domain
ls skills/bioinformatics/
# Output: sequence-analysis.md blast-search.md phylogenetics.md etc.

# Read a specific skill
cat skills/bioinformatics/sequence-analysis.md
```

#### 5. Using Individual Skills

Each skill file follows a consistent format:

```markdown
# Skill Name

## Description
Brief description of what the skill does

## Prerequisites
Required Python packages and dependencies

## Functions
- `function_name()`: Description
- `another_function()`: Description

## Usage Examples
```python
# Example code
from some_package import function
result = function(data)
```

## Integration
How to integrate with AI agents or workflows
```

**Example Usage:**

```python
# Load bioinformatics skills
import sys
sys.path.append('claude-scientific-skills/skills/bioinformatics')

# Import skill functions
from sequence_analysis import analyze_gc_content, translate_dna

# Use the skill
sequence = "ATGCGATCGTAGCTAGCTAG"
gc_content = analyze_gc_content(sequence)
protein = translate_dna(sequence)

print(f"GC Content: {gc_content}%")
print(f"Protein: {protein}")
```

#### 6. Integrating with AI Agents

**Method 1: Direct Import**
```python
# Create a skills manager
class SkillsManager:
    def __init__(self, skills_path):
        self.skills_path = skills_path
        self.loaded_skills = {}
    
    def load_skill(self, domain, skill_name):
        skill_path = f"{self.skills_path}/{domain}/{skill_name}.py"
        if os.path.exists(skill_path):
            spec = importlib.util.spec_from_file_location(skill_name, skill_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.loaded_skills[f"{domain}.{skill_name}"] = module
            return module
        return None
    
    def get_skill_function(self, domain_skill_function):
        domain, skill, function = domain_skill_function.split('.')
        if f"{domain}.{skill}" in self.loaded_skills:
            return getattr(self.loaded_skills[f"{domain}.{skill}"], function)
        return None

# Usage
skills_manager = SkillsManager("claude-scientific-skills/skills")
bio_skills = skills_manager.load_skill("bioinformatics", "sequence_analysis")
gc_function = skills_manager.get_skill_function("bioinformatics.sequence_analysis.analyze_gc_content")
```

**Method 2: MCP Server Integration**
```python
# Create an MCP server for skills
from mcp.server import Server
import json

app = Server("scientific-skills")

@app.list_tools()
async def list_tools():
    tools = []
    for domain in os.listdir("skills"):
        for skill_file in os.listdir(f"skills/{domain}"):
            if skill_file.endswith(".md"):
                skill_name = skill_file[:-3]
                tools.append({
                    "name": f"{domain}_{skill_name}",
                    "description": f"Scientific skill for {domain}: {skill_name}"
                })
    return tools

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    domain, skill = name.split("_", 1)
    # Load and execute the skill with arguments
    result = execute_skill(domain, skill, arguments)
    return {"content": [{"type": "text", "text": json.dumps(result)}]}
```

#### 7. Creating Custom Workflows

```python
# Example: Drug Discovery Workflow
class DrugDiscoveryWorkflow:
    def __init__(self, skills_manager):
        self.skills = skills_manager
        self.bio_skills = self.skills.load_skill("bioinformatics", "target_analysis")
        self.chem_skills = self.skills.load_skill("cheminformatics", "virtual_screening")
        self.ml_skills = self.skills.load_skill("machine-learning", "admet_prediction")
    
    def run_pipeline(self, target_protein, compound_library):
        # Step 1: Analyze target
        target_analysis = self.bio_skills.analyze_protein_target(target_protein)
        
        # Step 2: Virtual screening
        screening_results = self.chem_skills.screen_compounds(
            target_analysis["binding_site"], 
            compound_library
        )
        
        # Step 3: ADMET prediction
        admet_results = self.ml_skills.predict_admet(screening_results["hits"])
        
        # Step 4: Rank and filter
        final_candidates = self.rank_candidates(screening_results, admet_results)
        
        return {
            "target_analysis": target_analysis,
            "screening_results": screening_results,
            "admet_predictions": admet_results,
            "final_candidates": final_candidates
        }

# Usage
workflow = DrugDiscoveryWorkflow(skills_manager)
results = workflow.run_pipeline("EGFR", "compound_library.sdf")
```

#### 8. Contributing to the Repository

**How to Contribute:**
1. **Fork the repository**: https://github.com/K-Dense-AI/claude-scientific-skills/fork
2. **Create a new branch**: `git checkout -b new-skill-name`
3. **Add your skill** in the appropriate domain directory
4. **Follow the template** from existing skills
5. **Test thoroughly** with example data
6. **Submit a pull request**

**Skill Template:**
```markdown
# Skill Name

## Description
Clear, concise description of the scientific capability

## Prerequisites
- Python packages required
- External dependencies
- Data format requirements

## Functions
### `function_name(parameters)`
- **Purpose**: What the function does
- **Parameters**: Input descriptions
- **Returns**: Output descriptions
- **Example**: Usage example

## Scientific Background
Brief explanation of the scientific principles

## References
Relevant papers, documentation, or resources

## Integration Notes
How to integrate with AI agents or other skills
```

### Community Resources

**GitHub Resources:**
- **Issues**: https://github.com/K-Dense-AI/claude-scientific-skills/issues
- **Discussions**: https://github.com/K-Dense-AI/claude-scientific-skills/discussions
- **Pull Requests**: https://github.com/K-Dense-AI/claude-scientific-skills/pulls
- **Wiki**: https://github.com/K-Dense-AI/claude-scientific-skills/wiki

**External Resources:**
- **Video Tutorial**: https://www.youtube.com/watch?v=ZxbnDaD_FVg (Getting Started)
- **K-Dense Website**: https://k-dense.ai/
- **Community Discord**: [Link available on GitHub]
- **Documentation Site**: [Link available on GitHub]

### Example Projects Using the Skills

**1. Bioinformatics Pipeline:**
```python
# Complete genomics analysis pipeline
from claude_scientific_skills import *

# Load sequencing data
sequences = load_fastq("sample.fastq")

# Quality control
qc_results = quality_control(sequences)

# Alignment
aligned_reads = align_to_reference(sequences, "reference.fa")

# Variant calling
variants = call_variants(aligned_reads)

# Annotation
annotated_variants = annotate_variants(variants)

# Generate report
generate_genomics_report(qc_results, annotated_variants)
```

**2. Drug Discovery Project:**
```python
# Virtual screening workflow
target = load_protein_structure("target.pdb")
compounds = load_compound_library("library.sdf")

# Prepare target
prepared_target = prepare_protein(target)

# Virtual screening
screening_results = virtual_screen(prepared_target, compounds)

# Molecular docking
docking_results = dock_compounds(prepared_target, screening_results.top_hits)

# ADMET prediction
admet_results = predict_admet(docking_results)

# Generate report
generate_drug_discovery_report(screening_results, docking_results, admet_results)
```

### Best Practices

1. **Start Simple**: Begin with basic skills before complex workflows
2. **Check Dependencies**: Ensure all required packages are installed
3. **Validate Inputs**: Always validate data formats and parameters
4. **Handle Errors**: Implement proper error handling and logging
5. **Document Everything**: Clear documentation is essential for reproducibility
6. **Test Thoroughly**: Validate results with known datasets
7. **Stay Updated**: Regularly pull updates from the repository
8. **Contribute Back**: Share improvements and new skills with the community

### Troubleshooting Common Issues

**Import Errors:**
```bash
# If you get import errors, check:
python -c "import biopython; print('BioPython OK')"
python -c "import rdkit; print('RDKit OK')"
python -c "import scanpy; print('Scanpy OK')"

# Install missing packages
pip install missing-package-name
```

**Path Issues:**
```python
# Add skills to Python path
import sys
sys.path.append('/path/to/claude-scientific-skills/skills')
```

**Version Conflicts:**
```bash
# Create a dedicated environment
python -m venv k-dense-skills
source k-dense-skills/bin/activate
pip install -r requirements.txt
```

## Free Tools and Open Source Components

K-Dense leverages several freely available tools and technologies:

### Core Technologies

1. **AI Model Providers**:
   - **OpenRouter**: Access to 40+ AI models (free tier available)
   - **OpenAI API**: GPT models with free usage limits
   - **Anthropic Claude**: Advanced reasoning capabilities
   - **Google Gemini**: Multi-modal AI capabilities
   - **xAI Grok**: Real-time information processing
   - **Qwen**: Open-source Chinese language models

2. **Scientific Python Ecosystem**:
   - **BioPython**: Computational biology and bioinformatics
   - **RDKit**: Cheminformatics and molecular modeling
   - **Scanpy**: Single-cell analysis
   - **scikit-learn**: Machine learning and data science
   - **PyTorch**: Deep learning framework
   - **statsmodels**: Statistical modeling
   - **NetworkX**: Network analysis and graph theory

3. **Database Access Libraries**:
   - **BioServices**: Access to 30+ biological databases
   - **EDGAR API**: SEC financial data
   - **NASA APIs**: Astronomical and earth science data
   - **PubMed API**: Medical literature database
   - **ChEMBL**: Bioactivity data for drug discovery
   - **UniProt**: Protein sequence and functional data

4. **File Format Support**:
   - **PyDICOM**: Medical imaging (DICOM files)
   - **pyfastx**: Genomics files (FASTA/FASTQ)
   - **pysam**: Bioinformatics file formats (BAM/SAM)
   - **pyteomics**: Mass spectrometry data (mzML)
   - **astropy**: Astronomy data (FITS files)
   - **pymatgen**: Materials science (CIF/POSCAR)

5. **Web and Infrastructure**:
   - **FastAPI**: Modern Python web framework
   - **Streamlit**: Quick web app development
   - **Docker**: Containerization for reproducible environments
   - **Modal**: Cloud compute platform (free tier available)
   - **MCP (Model Context Protocol)**: Extensible AI tool integration

## Replicating K-Dense with Free Tools

### Step-by-Step Implementation Guide

#### 1. Setup Basic Infrastructure

```bash
# Create project structure
mkdir k-dense-clone
cd k-dense-clone
python -m venv venv
source venv/bin/activate

# Install core dependencies
pip install openai anthropic google-generativeai
pip install fastapi uvicorn streamlit
pip install biopython rdkit scanpy scikit-learn
pip install torch torchvision
pip install requests beautifulsoup4
pip install pandas numpy matplotlib seaborn
```

#### 2. Create AI Agent System

```python
# agent_system.py
import openai
import anthropic
from typing import List, Dict, Any

class ScientificAgent:
    def __init__(self, api_keys: Dict[str, str]):
        self.api_keys = api_keys
        self.setup_clients()
        
    def setup_clients(self):
        # Setup multiple AI model clients
        self.openai_client = openai.OpenAI(api_key=self.api_keys['openai'])
        self.anthropic_client = anthropic.Anthropic(api_key=self.api_keys['anthropic'])
        
    def analyze_task(self, user_input: str) -> Dict[str, Any]:
        # Use main agent to analyze and delegate tasks
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a scientific task analyzer. Determine the domain and required expertise."},
                {"role": "user", "content": user_input}
            ]
        )
        return response.choices[0].message.content
    
    def delegate_to_expert(self, task: str, domain: str) -> str:
        # Delegate to specialized expert based on domain
        expert_prompt = self.get_expert_prompt(domain)
        response = self.anthropic_client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4000,
            messages=[
                {"role": "user", "content": f"{expert_prompt}\n\nTask: {task}"}
            ]
        )
        return response.content[0].text
```

#### 3. Implement Scientific Skills

```python
# bioinformatics_skills.py
from Bio import SeqIO, AlignIO
from Bio.Blast import NCBIWWW
import pandas as pd
import numpy as np

class BioinformaticsSkills:
    def __init__(self):
        self.databases = {
            'ncbi': 'https://www.ncbi.nlm.nih.gov/',
            'uniprot': 'https://www.uniprot.org/',
            'ensembl': 'https://www.ensembl.org/'
        }
    
    def analyze_sequence(self, sequence: str, format_type: str = 'fasta') -> Dict:
        """Analyze DNA/protein sequence"""
        try:
            seq_record = SeqIO.read(sequence, format_type)
            return {
                'length': len(seq_record.seq),
                'gc_content': self.calculate_gc_content(seq_record.seq),
                'translation': str(seq_record.seq.translate()) if 'DNA' in str(seq_record.seq.alphabet) else None
            }
        except Exception as e:
            return {'error': str(e)}
    
    def calculate_gc_content(self, sequence) -> float:
        gc_count = sequence.count('G') + sequence.count('C')
        return (gc_count / len(sequence)) * 100 if len(sequence) > 0 else 0
    
    def blast_search(self, sequence: str) -> Dict:
        """Perform BLAST search"""
        try:
            result_handle = NCBIWWW.qblast("blastn", "nt", sequence)
            # Parse results (simplified)
            return {'status': 'BLAST search initiated', 'result_handle': str(result_handle)}
        except Exception as e:
            return {'error': f'BLAST search failed: {str(e)}'}

# cheminformatics_skills.py
from rdkit import Chem
from rdkit.Chem import Descriptors, Draw
import pandas as pd

class CheminformaticsSkills:
    def __init__(self):
        self.descriptors = [x[0] for x in Descriptors._descList]
    
    def analyze_molecule(self, smiles: str) -> Dict:
        """Analyze molecular properties"""
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return {'error': 'Invalid SMILES string'}
            
            properties = {}
            for desc in self.descriptors[:10]:  # Limit to first 10 descriptors
                try:
                    properties[desc] = getattr(Descriptors, desc)(mol)
                except:
                    continue
            
            return {
                'smiles': smiles,
                'molecular_weight': Descriptors.MolWt(mol),
                'logp': Descriptors.MolLogP(mol),
                'num_atoms': mol.GetNumAtoms(),
                'properties': properties
            }
        except Exception as e:
            return {'error': str(e)}
```

#### 4. Database Integration

```python
# database_access.py
import requests
import pandas as pd
from typing import Dict, List

class ScientificDatabaseAccess:
    def __init__(self):
        self.endpoints = {
            'pubmed': 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/',
            'chembl': 'https://www.ebi.ac.uk/chembl/api/data/',
            'uniprot': 'https://rest.uniprot.org/'
        }
    
    def search_pubmed(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search PubMed for articles"""
        try:
            search_url = f"{self.endpoints['pubmed']}esearch.fcgi"
            search_params = {
                'db': 'pubmed',
                'term': query,
                'retmode': 'json',
                'retmax': max_results
            }
            
            search_response = requests.get(search_url, params=search_params)
            search_data = search_response.json()
            
            if 'esearchresult' in search_data and 'idlist' in search_data['esearchresult']:
                pmids = search_data['esearchresult']['idlist']
                
                # Fetch summaries
                summary_url = f"{self.endpoints['pubmed']}esummary.fcgi"
                summary_params = {
                    'db': 'pubmed',
                    'id': ','.join(pmids),
                    'retmode': 'json'
                }
                
                summary_response = requests.get(summary_url, params=summary_params)
                return summary_response.json()
            
            return {'error': 'No results found'}
        except Exception as e:
            return {'error': str(e)}
    
    def get_chembl_compounds(self, target_chembl_id: str) -> Dict:
        """Get compounds from ChEMBL"""
        try:
            url = f"{self.endpoints['chembl']}compound"
            params = {'target_chembl_id': target_chembl_id, 'format': 'json'}
            
            response = requests.get(url, params=params)
            return response.json()
        except Exception as e:
            return {'error': str(e)}
```

#### 5. Web Interface

```python
# app.py
import streamlit as st
from agent_system import ScientificAgent
from bioinformatics_skills import BioinformaticsSkills
from cheminformatics_skills import CheminformaticsSkills
from database_access import ScientificDatabaseAccess

def main():
    st.title("K-Dense Clone - AI Co-Scientist")
    
    # Sidebar for API keys
    with st.sidebar:
        st.header("API Keys")
        openai_key = st.text_input("OpenAI API Key", type="password")
        anthropic_key = st.text_input("Anthropic API Key", type="password")
        
        if openai_key and anthropic_key:
            api_keys = {'openai': openai_key, 'anthropic': anthropic_key}
            agent = ScientificAgent(api_keys)
            bio_skills = BioinformaticsSkills()
            chem_skills = CheminformaticsSkills()
            db_access = ScientificDatabaseAccess()
            st.success("Agents initialized!")
    
    # Main interface
    st.header("Ask a Scientific Question")
    user_input = st.text_area("Enter your research question or task:")
    
    if st.button("Analyze") and 'agent' in locals():
        with st.spinner("Analyzing task..."):
            task_analysis = agent.analyze_task(user_input)
            st.subheader("Task Analysis")
            st.write(task_analysis)
        
        # Domain-specific tools
        domain = st.selectbox("Select domain:", ["Bioinformatics", "Cheminformatics", "Database Search"])
        
        if domain == "Bioinformatics":
            st.subheader("Bioinformatics Tools")
            sequence_input = st.text_area("Enter DNA/Protein sequence:")
            if st.button("Analyze Sequence"):
                result = bio_skills.analyze_sequence(sequence_input)
                st.json(result)
        
        elif domain == "Cheminformatics":
            st.subheader("Cheminformatics Tools")
            smiles_input = st.text_input("Enter SMILES string:")
            if st.button("Analyze Molecule"):
                result = chem_skills.analyze_molecule(smiles_input)
                st.json(result)
        
        elif domain == "Database Search":
            st.subheader("Database Search")
            search_query = st.text_input("Search PubMed:")
            if st.button("Search"):
                result = db_access.search_pubmed(search_query)
                st.json(result)

if __name__ == "__main__":
    main()
```

#### 6. Deployment with Docker

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8501:8501"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    volumes:
      - ./data:/app/data
```

```txt
# requirements.txt
openai>=1.0.0
anthropic>=0.3.0
streamlit>=1.28.0
fastapi>=0.100.0
uvicorn>=0.23.0
biopython>=1.81
rdkit-pypi>=2023.3.2
scanpy>=1.9.0
scikit-learn>=1.3.0
torch>=2.0.0
pandas>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
seaborn>=0.12.0
requests>=2.31.0
beautifulsoup4>=4.12.0
```

### Advanced Features Implementation

#### Workflow System

```python
# workflow_system.py
from typing import Dict, List, Any
import json

class ScientificWorkflow:
    def __init__(self):
        self.workflows = self.load_workflows()
    
    def load_workflows(self) -> Dict:
        # Load predefined scientific workflows
        return {
            'drug_discovery': {
                'name': 'Drug Discovery Pipeline',
                'steps': [
                    {'name': 'Target Identification', 'skill': 'bioinformatics'},
                    {'name': 'Virtual Screening', 'skill': 'cheminformatics'},
                    {'name': 'ADMET Prediction', 'skill': 'cheminformatics'},
                    {'name': 'Lead Optimization', 'skill': 'molecular_modeling'}
                ],
                'required_data': ['target_protein', 'compound_library']
            },
            'genomics_analysis': {
                'name': 'Genomics Analysis Pipeline',
                'steps': [
                    {'name': 'Quality Control', 'skill': 'bioinformatics'},
                    {'name': 'Alignment', 'skill': 'bioinformatics'},
                    {'name': 'Variant Calling', 'skill': 'genomics'},
                    {'name': 'Annotation', 'skill': 'bioinformatics'}
                ],
                'required_data': ['raw_sequencing_data']
            }
        }
    
    def execute_workflow(self, workflow_name: str, inputs: Dict) -> Dict:
        if workflow_name not in self.workflows:
            return {'error': 'Workflow not found'}
        
        workflow = self.workflows[workflow_name]
        results = {}
        
        for step in workflow['steps']:
            # Execute each step with appropriate skill
            results[step['name']] = self.execute_step(step, inputs)
        
        return {
            'workflow': workflow_name,
            'results': results,
            'status': 'completed'
        }
    
    def execute_step(self, step: Dict, inputs: Dict) -> Dict:
        # Implementation would call appropriate skill
        return {'step': step['name'], 'status': 'completed', 'output': 'Step output'}
```

#### File Format Support

```python
# file_processor.py
from typing import Dict, Any
import pandas as pd
import json

# Import format-specific libraries
try:
    from Bio import SeqIO
    BIOPYTHON_AVAILABLE = True
except ImportError:
    BIOPYTHON_AVAILABLE = False

try:
    from rdkit import Chem
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False

class ScientificFileProcessor:
    def __init__(self):
        self.supported_formats = {
            # Genomics formats
            '.fasta': self.process_fasta,
            '.fastq': self.process_fastq,
            '.bam': self.process_bam,
            '.vcf': self.process_vcf,
            
            # Chemistry formats
            '.sdf': self.process_sdf,
            '.mol': self.process_mol,
            '.smiles': self.process_smiles,
            
            # Data formats
            '.csv': self.process_csv,
            '.tsv': self.process_tsv,
            '.json': self.process_json,
            '.xlsx': self.process_excel,
            
            # Imaging formats
            '.tiff': self.process_tiff,
            '.png': self.process_image,
            '.jpg': self.process_image,
        }
    
    def process_file(self, file_path: str) -> Dict[str, Any]:
        file_extension = file_path.lower().split('.')[-1]
        
        if f'.{file_extension}' not in self.supported_formats:
            return {'error': f'Unsupported file format: .{file_extension}'}
        
        try:
            processor = self.supported_formats[f'.{file_extension}']
            return processor(file_path)
        except Exception as e:
            return {'error': f'Error processing file: {str(e)}'}
    
    def process_fasta(self, file_path: str) -> Dict:
        if not BIOPYTHON_AVAILABLE:
            return {'error': 'BioPython not available'}
        
        sequences = []
        for record in SeqIO.parse(file_path, 'fasta'):
            sequences.append({
                'id': record.id,
                'description': record.description,
                'sequence': str(record.seq),
                'length': len(record.seq)
            })
        
        return {
            'format': 'FASTA',
            'num_sequences': len(sequences),
            'sequences': sequences
        }
    
    def process_csv(self, file_path: str) -> Dict:
        try:
            df = pd.read_csv(file_path)
            return {
                'format': 'CSV',
                'shape': df.shape,
                'columns': df.columns.tolist(),
                'preview': df.head().to_dict('records'),
                'data_types': df.dtypes.to_dict()
            }
        except Exception as e:
            return {'error': f'Error reading CSV: {str(e)}'}
    
    def process_smiles(self, file_path: str) -> Dict:
        if not RDKIT_AVAILABLE:
            return {'error': 'RDKit not available'}
        
        try:
            with open(file_path, 'r') as f:
                smiles_list = [line.strip() for line in f if line.strip()]
            
            molecules = []
            for i, smiles in enumerate(smiles_list):
                mol = Chem.MolFromSmiles(smiles)
                if mol:
                    molecules.append({
                        'index': i,
                        'smiles': smiles,
                        'valid': True,
                        'num_atoms': mol.GetNumAtoms()
                    })
                else:
                    molecules.append({
                        'index': i,
                        'smiles': smiles,
                        'valid': False
                    })
            
            return {
                'format': 'SMILES',
                'total_molecules': len(molecules),
                'valid_molecules': len([m for m in molecules if m['valid']]),
                'molecules': molecules
            }
        except Exception as e:
            return {'error': f'Error processing SMILES: {str(e)}'}
```

#### Database Integration

```python
# enhanced_database.py
import requests
import pandas as pd
from typing import Dict, List, Any
import time

class EnhancedDatabaseAccess:
    def __init__(self):
        self.rate_limits = {
            'pubmed': 3,  # requests per second
            'chembl': 10,
            'uniprot': 15
        }
        self.last_request = {}
    
    def rate_limit_check(self, database: str):
        if database in self.last_request:
            elapsed = time.time() - self.last_request[database]
            min_interval = 1.0 / self.rate_limits[database]
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
        self.last_request[database] = time.time()
    
    def search_pubmed_advanced(self, query: str, max_results: int = 50, 
                             publication_date: str = None, 
                             article_type: str = None) -> Dict:
        """Advanced PubMed search with filters"""
        self.rate_limit_check('pubmed')
        
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            'db': 'pubmed',
            'term': query,
            'retmode': 'json',
            'retmax': max_results
        }
        
        # Add filters
        if publication_date:
            params['term'] += f" AND ({publication_date}[Date - Publication])"
        if article_type:
            params['term'] += f" AND ({article_type}[Publication Type])"
        
        try:
            search_response = requests.get(base_url, params=params)
            search_data = search_response.json()
            
            if 'esearchresult' in search_data:
                pmids = search_data['esearchresult']['idlist']
                
                # Fetch detailed information
                summaries = self.fetch_pubmed_details(pmids)
                return {
                    'query': query,
                    'total_results': len(pmids),
                    'articles': summaries
                }
            
            return {'error': 'No results found'}
        except Exception as e:
            return {'error': str(e)}
    
    def fetch_pubmed_details(self, pmids: List[str]) -> List[Dict]:
        """Fetch detailed article information"""
        self.rate_limit_check('pubmed')
        
        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        params = {
            'db': 'pubmed',
            'id': ','.join(pmids),
            'retmode': 'json'
        }
        
        response = requests.get(summary_url, params=params)
        data = response.json()
        
        articles = []
        if 'result' in data:
            for pmid in pmids:
                if pmid in data['result']:
                    article_data = data['result'][pmid]
                    articles.append({
                        'pmid': pmid,
                        'title': article_data.get('title', ''),
                        'authors': article_data.get('authors', []),
                        'journal': article_data.get('source', ''),
                        'pubdate': article_data.get('pubdate', ''),
                        'abstract': article_data.get('abstract', '')
                    })
        
        return articles
```

## Cost Comparison

### Free Implementation Costs

| Component | Cost | Notes |
|-----------|------|-------|
| Hosting | $0-20/month | Self-hosted on cloud platforms (free tier) |
| Storage | $0-10/month | Local storage or cloud storage free tier |
| Compute | $0-50/month | Free tier cloud compute or local machine |
| API Calls | $0-200/month | Free tiers of various AI model providers |
| Databases | $0/month | Most scientific databases are free |
| **Total** | **$0-280/month** | Depending on scale and usage |

### K-Dense Web Subscription Costs

| Plan | Monthly Cost | Features |
|------|-------------|----------|
| Free | $0 | Basic features, limited compute |
| Pro | $29-49/month | Advanced features, more compute |
| Business | $99-199/month | Collaboration, advanced analytics |
| Enterprise | $500+/month | Custom features, dedicated support |

### API Cost Breakdown (Free Implementation)

| Service | Free Tier | Cost After Free Tier |
|----------|-----------|----------------------|
| OpenAI GPT-4 | $5 credit | $0.03-0.06 per 1K tokens |
| Anthropic Claude | $5 credit | $0.015-0.075 per 1K tokens |
| Google Gemini | Free tier available | Varies by model |
| OpenRouter | $5 credit | Aggregated pricing |
| Modal (cloud compute) | $30 credit | $0.0004 per GPU-second |

## Recommendations

### For Individual Researchers

1. **Start with K-Dense BYOK** - Free and open-source
2. **Use free API tiers** from multiple providers
3. **Leverage local compute** for smaller tasks
4. **Use Modal** for occasional heavy workloads
5. **Focus on specific skills** relevant to your field

**Setup Time:** 2-4 hours
**Monthly Cost:** $0-50
**Best For:** Learning, prototyping, small-scale projects

### For Research Groups

1. **Consider K-Dense Web** for collaboration features
2. **Implement shared API key management**
3. **Set up local infrastructure** for sensitive data
4. **Use hybrid approach** - local for routine tasks, cloud for heavy compute
5. **Standardize workflows** across the group

**Setup Time:** 1-2 days
**Monthly Cost:** $100-500
**Best For:** Team collaboration, medium-scale projects

### For Institutions

1. **Enterprise K-Dense Web** for full features and support
2. **Implement proper security and compliance**
3. **Integrate with existing systems** (LIMS, data warehouses)
4. **Provide training and documentation**
5. **Establish governance policies**

**Setup Time:** 1-2 weeks
**Monthly Cost:** $500-5000+
**Best For:** Large-scale operations, compliance requirements

## Getting Started Resources

### Official Resources

- **K-Dense Web**: https://app.k-dense.ai/
- **K-Dense BYOK GitHub**: https://github.com/K-Dense-AI/k-dense-byok
- **Claude Scientific Skills**: https://github.com/K-Dense-AI/claude-scientific-skills
- **Documentation**: Available in respective GitHub repositories
- **Community**: GitHub discussions, issues, and community forums

### Required Accounts for Free Setup

1. **OpenRouter.ai** - For accessing multiple AI models
2. **API Keys** from at least one provider:
   - OpenAI (GPT models)
   - Anthropic (Claude models)
   - Google (Gemini models)
3. **Optional**: Modal.com account for cloud compute
4. **WSL** (Windows) or native Linux/macOS environment

### Installation Commands

```bash
# Clone the repositories
git clone https://github.com/K-Dense-AI/k-dense-byok.git
git clone https://github.com/K-Dense-AI/claude-scientific-skills.git

# Setup K-Dense BYOK
cd k-dense-byok
# Follow the setup instructions in the README

# Install scientific skills (optional)
cd ../claude-scientific-skills
# Copy skills to your agent's skills directory
```

## Conclusion

K-Dense represents a significant advancement in AI-powered scientific research tools, offering three distinct approaches to suit different needs:

**K-Dense BYOK** provides a free, open-source foundation that demonstrates how AI agents can be enhanced with specialized scientific skills. It's ideal for individual researchers who want to understand the technology and customize their workflows.

**K-Dense Web** offers a polished, cloud-based solution with advanced features, collaboration tools, and professional support - suitable for teams and institutions that need reliability and scalability.

**Claude Scientific Skills** serves as the open-source core, providing the specialized expertise that makes these systems truly useful for scientific work.

The choice between these approaches depends on your specific needs:
- **Budget constraints** (free vs. paid)
- **Technical expertise** (setup vs. ready-to-use)
- **Scale requirements** (individual vs. team vs. institution)
- **Security needs** (local vs. cloud)
- **Support requirements** (community vs. professional)

For most researchers, starting with the free BYOK version provides valuable insights into the technology while allowing for customization based on specific research needs. As requirements grow, the transition to K-Dense Web offers a seamless path to enhanced capabilities and professional support.

The modular nature of the ecosystem means you can start small and scale up as needed, making advanced AI-powered research accessible to everyone from individual scientists to large research institutions.

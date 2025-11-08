# Cloud execution overview

GOLIAT supports multiple execution strategies for scaling beyond local hardware. Each method has trade-offs between cost, complexity, and true parallel execution.

## Execution methods

### Local sequential

Run simulations one at a time on your local machine. Simple, free, but slow for large studies.

### Local parallel

Split a study into multiple processes that run simultaneously. Setup and extract phases benefit from parallelization, but iSolve run phases queue sequentially on a single GPU. Only one iSolve instance can execute at a time per GPU.

**Limitation**: True parallel iSolve execution requires multiple GPUs. Local parallel speeds up setup and extract, not the run phase.

### oSPARC batch

Submit simulations to the oSPARC cloud platform. Each job gets its own GPU, enabling true parallel execution. Requires API credentials and platform access.

**How it works**: oSPARC only handles the run phase. Users are responsible for running setup and extraction locally themselves. If you use Sim4Life Python Runner on the oSPARC cloud for setup/extraction, you'll need additional licenses for those phases (beyond your local licenses).

**Limitation**: ~61 concurrent job limit, costs scale with compute time.

### Distributed cloud VMs

Deploy multiple Windows VMs, each with its own GPU. Coordinate via the monitoring dashboard. Scales indefinitely, true parallel execution, centralized monitoring.

**Best for**: Large studies requiring true parallel iSolve execution across many simulations.

## Comparison

| Feature | Local sequential | Local parallel | oSPARC batch | Distributed VMs |
|:---|:---:|:---:|:---:|:---:|
| True parallel iSolve | ✗ | ✗ | ✓ | ✓ |
| Multiple GPUs | ✗ | ✗ | ✓ | ✓ |
| Setup cost | Free | Free | API credentials | VM deployment |
| Run cost | Free | Free | Per job | Per hour |
| License required | Local | Local | Local (setup/extract), cloud (if using Python Runner) | Local (per VM, can use license server) |
| Scalability | Single machine | Single machine | ~61 jobs | Unlimited |
| Monitoring | Local GUI | Local GUI | oSPARC dashboard | Monitoring dashboard |
| Coordination | Manual | Manual | Automatic | Automatic (super studies) |
| Best for | 1-10 sims | 10-50 sims | 50-500+ sims | Any scale |

**True parallel iSolve**: Multiple simulations run simultaneously, each using its own GPU. Local parallel only parallelizes setup/extract phases; run phases queue sequentially on a single GPU.

**Distributed VMs** provide true parallel execution, unlimited scalability, and centralized monitoring. The monitoring dashboard coordinates super studies across workers automatically. Communication is bidirectional: workers download assignment configs (split from a master config) from the dashboard, and report progress back in real-time.

## Visualization

The following diagram illustrates the different execution architectures:

![Execution architectures](../img/cloud/execution_architectures.svg)

**Key differences**:

- **Local sequential/parallel**: Single machine, single GPU. Parallel only helps setup/extract.
- **oSPARC**: Cloud platform handles run phase only. Users handle setup/extract locally. If using Sim4Life Python Runner on oSPARC cloud for setup/extract, additional licenses required. Has ~61 job limit.
- **Distributed VMs**: Multiple machines, each with dedicated GPU. Monitoring dashboard splits master config into assignments and distributes them to workers. Workers download assignments, run simulations, and report progress back. Scales without platform limits.

## Choosing a method

**1-10 simulations**: Local sequential is simplest.

**10-50 simulations**: Local parallel speeds up setup/extract. Run phase remains sequential.

**50-500+ simulations**: oSPARC batch if you have platform access and want managed execution.

**Any scale, true parallel**: Distributed cloud VMs with monitoring dashboard. Best for large studies requiring guaranteed parallel execution without platform constraints.

## Related documentation

- [oSPARC](osparc.md): Cloud batch execution via oSPARC platform
- [Monitoring dashboard](monitoring.md): Web-based coordination for distributed VMs
- [Super Studies](super_studies.md): Distributed execution across multiple workers
- [Cloud setup](cloud_setup.md): Deploying and configuring cloud GPU instances

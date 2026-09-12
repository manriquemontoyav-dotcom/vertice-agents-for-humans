from .protocol import Action, WorkflowStep

def proposal_workflow():
    names=[
        'Read request','Extract mandatory requirements','Normalize dates','Identify constraints',
        'Search candidate suppliers','Collect public pricing','Check supplier availability','Compare alternatives',
        'Score alternatives','Select best-fit supplier','Calculate base cost','Calculate taxes','Calculate delivery',
        'Calculate margin','Run price sensitivity','Draft proposal','Insert commercial terms','Check arithmetic',
        'Check required documents','Check compliance matrix','Check deadline','Check recipient','Generate summary',
        'Generate evidence bundle','Prepare submission payload','Final consistency check']
    steps=[WorkflowStep(n,Action('work_step',{'step':n})) for n in names]
    steps.append(WorkflowStep('Submit exact proposal',Action('submit_proposal',{
        'recipient':'Demo Buyer','proposal_id':'AFH-DEMO-001','amount_usd':8750
    },8750,True,True,'Demo Buyer')))
    return steps

# monday.com Project Prompts

Copy-paste prompts for creating and managing projects in monday.com via Claude
(the `monday-*` skills in `.claude/skills/` + the monday MCP server).
Each prompt triggers the matching skill automatically — no need to name the skill.

Replace anything in `<angle brackets>` with your real values before sending.

---

## 1. Project & engineering boards (`monday-board-setup`)

1. Create a board called "Machine Installation — <customer>" with groups Pre-Delivery, Shipping, Installation, FAT/SAT, Handover, and columns: owner, status, due date, priority, customer contact, and a files column for CAD drawings.
2. Set up a project tracker for the ROTOCON website relaunch with groups Backlog, In Progress, Review, Done, and columns for owner, status, deadline, and effort estimate in days.
3. Create a bug tracker board for the n8n email assistant with columns: severity (Critical/High/Medium/Low), reporter, assignee, status, date reported, and a long-text column for reproduction steps.
4. Build a sprint board for the monday_rotocon v0.2.0 milestone with groups Sprint Backlog, This Week, In Review, Done, and a numbers column for story points.
5. Create a board to track spare-parts orders with groups New, Quoted, Ordered, Shipped, Delivered, and columns: customer, machine model, part number, quantity, price, and expected delivery date.
6. Set up a board for trade-show planning (LOUPE Americas 2026) with groups 90 Days Out, 60 Days Out, 30 Days Out, Show Week, Follow-up, and columns for owner, budget, status, and vendor.
7. Create a content calendar board for the ROTOCON magazine with groups per month, and columns: author, content type (article/video/social), status, publish date, and target channel.
8. Build a machine refurbishment board with one group per machine currently in the workshop and columns: technician, incoming condition, tasks remaining, target ready date, and status.
9. Create a document-approval board for CAD drawings with groups Submitted, Under Review, Changes Requested, Approved, and columns: drawing number, revision, reviewer, and decision date.
10. Set up an onboarding board for new dealers with groups Contract, Training, Demo Equipment, First Order, and columns: region, owner, status, and start date.
11. Create a board for tracking software licenses and subscriptions with columns: vendor, cost per month, renewal date, owner, and seats used, grouped by department.
12. Build a risk register board for the digital-transformation program with columns: risk description, probability, impact, mitigation owner, status, and review date.
13. Create a supplier evaluation board with groups per supplier category (electronics, mechanical, consumables) and columns: contact, last audit date, rating, and open issues.
14. Set up a quarterly OKR board with one group per team, columns for objective owner, key result, progress (%), confidence, and status.
15. Create a warehouse/logistics board tracking outbound machine shipments with columns: customer, destination country, freight forwarder, Incoterm, crate-ready date, ETD, ETA, and customs status.

## 2. CRM & sales pipelines (`monday-board-setup` + `monday-task-management`)

16. Create a sales pipeline board with groups Lead, Qualified, Demo Scheduled, Quote Sent, Negotiation, Won, Lost, and columns: company, contact, machine of interest, deal value in EUR, expected close date, and owner.
17. Set up a lead-capture board for LOUPE Americas booth 719 with columns: name, company, country, email, phone, machine interest, lead temperature (Hot/Warm/Cold), and follow-up owner.
18. Create a quote-tracking board with columns: quote number, customer, machine configuration, amount, sent date, valid-until date, and status (Draft/Sent/Accepted/Expired).
19. Build an account-management board with one item per key customer, columns for account owner, region, installed machines, last contact date, next planned touchpoint, and health status.
20. Create a distributor performance board grouped by region (USA, Europe, Africa, Asia) with columns: distributor name, YTD revenue, open opportunities, and last quarterly review date.
21. Add a new deal to the sales pipeline: <company>, interested in an RFP 460, deal value <amount>, expected close <date>, owner George — put it in the Qualified group.
22. Move all deals in "Quote Sent" older than 30 days to a "Needs follow-up" group and assign them to me.
23. Create a win/loss analysis board where each closed deal gets an item with columns: outcome, competitor, decisive factor, deal size, and sales cycle length in days.

## 3. Service & support (`monday-board-setup` + `monday-task-management`)

24. Create a service-ticket board with groups New, In Progress, Waiting on Customer, Waiting on Parts, Resolved, and columns: customer, machine serial number, issue category, technician, SLA due date, and priority.
25. Set up a preventive-maintenance board with one item per installed machine, columns: customer, serial number, last service date, next service due, assigned technician, and contract type.
26. Create a technician dispatch board for this month with groups per week and columns: technician, customer site, country, travel booked (checkbox), and job status.
27. Build a warranty-claims board with columns: customer, machine, part affected, claim date, decision (Approved/Rejected/Pending), replacement shipped date, and cost.
28. Create an RMA (returns) board with groups Requested, Authorized, Received, Inspected, Closed, and columns: customer, part number, reason, and credit note issued.
29. Log a new service ticket: <customer> reports <issue> on machine serial <number>, priority High, assign to <technician>, SLA due in 48 hours.
30. Create a training-sessions board tracking operator training at customer sites with columns: customer, trainer, dates, attendees count, certificate issued (checkbox), and follow-up notes.

## 4. Internal operations & HR (`monday-board-setup`)

31. Create an employee-onboarding board with groups Before Day 1, First Week, First Month, First Quarter, and columns: new hire, buddy, task owner, status, and due date.
32. Set up a recruitment pipeline with groups Applied, Screening, Interview 1, Interview 2, Offer, Hired, and columns: candidate, role, recruiter, source, and salary expectation.
33. Create a vacation/absence planning board grouped by team with columns: person, type (vacation/sick/training), start date, end date, and approval status.
34. Build a company-fleet board with one item per vehicle, columns: driver, license plate, next inspection (TÜV) date, leasing end date, and mileage.
35. Create an IT asset board with columns: device type, assigned to, purchase date, warranty end, and condition, grouped by device category.
36. Set up a meeting-actions board where every item is an action from the weekly management meeting, with columns: owner, source meeting date, due date, and status.
37. Create a compliance/audit board for ISO certification tasks with groups per audit chapter and columns: responsible, evidence link, status, and audit date.

## 5. Everyday task management (`monday-task-management`)

38. Create a task "Prepare FAT protocol for <customer>" on the <board> board, assign it to me, due Friday, priority High.
39. Update the status of "<item>" on <board> to Done and add a comment summarizing what was delivered.
40. Reassign all open items owned by <person> on the <board> board to <other person> and add a comment explaining the handover.
41. Create subitems under "<item>" for: electrical check, mechanical alignment, test print run, and customer sign-off — each with its own due date next week.
42. Find every item on <board> that is overdue and set its priority to Critical.
43. Add a comment to "<item>" tagging <person>: the shipment is delayed by one week, new ETA <date>.
44. Move all Done items from the current sprint group to an Archive group on the same board.
45. Create ten items on the trade-show board from this list: <paste list> — put them in the "30 Days Out" group with me as owner.
46. Change the due date of every item in the "Installation" group on the <customer> board by +14 days — the machine cleared customs late.

## 6. Docs (`monday-docs-collaborator`)

47. Create a monday doc "Weekly Ops Update — <date>" that embeds the live status column of the top 10 open items from the <board> board, with sections for Wins, Risks, and Next Week.
48. Draft an RFC doc for migrating the weekly report from n8n to the monday-native automation, with sections Background, Proposal, Alternatives, and Decision, and tag <person> for review.
49. Create a runbook doc "Machine Installation Playbook" with a checklist section per installation phase, linked to the installation board template.
50. Summarize today's management meeting into a new monday doc and create one task on the meeting-actions board per action item mentioned.
51. Add a "Post-mortem: <incident>" doc with sections Timeline, Root Cause, What Went Well, What Went Wrong, and Action Items, and embed the related service tickets.

## 7. Forms (`monday-forms-builder`)

52. Create an intake form "Service Request" feeding the service-ticket board, with questions: company, contact email, machine serial number, issue description, urgency, and photo upload.
53. Build a public lead-capture form for the website feeding the sales pipeline board: name, company, country, machine of interest (dropdown), message — and give me the shareable link.
54. Create an internal purchase-request form feeding a procurement board with questions: requester, item, supplier, estimated cost, budget line, and justification.
55. Set up a trade-show feedback form for booth visitors: how did you hear about us, products of interest, rating, and permission to contact — feeding the LOUPE leads board.
56. Add a "preferred installation window" date question to the existing Service Request form and republish it.

## 8. Status & reporting (`monday-project-status-report`)

57. Give me a status report for the <board> board: what's overdue, what's blocked, and who is overloaded.
58. Generate a weekly update across the sales pipeline and service-ticket boards: new deals, deals closed, tickets opened vs. resolved, and anything breaching SLA.
59. Show me the workload distribution on the installation board — items per person, flagged if anyone has more than 8 open items.
60. Compare progress on the <board> board against last week: what moved to Done, what slipped, and what's newly overdue.
61. Produce a management-ready summary of all boards in the <workspace> workspace: one paragraph per board with overall health, top risk, and next milestone.

---

## Tips

- **Be specific about columns and groups** — the skills create exactly what you
  describe; vague prompts produce generic boards.
- **Chain prompts**: create the board first, then a second prompt to bulk-add
  items, then a form feeding it, then a recurring status report.
- **Read-only by default in this repo**: the `monday_rotocon` Python package
  never writes to monday. All prompts above act through the monday **MCP
  server**, which is the sanctioned write path (see CLAUDE.md).
- Only section 8 (`monday-project-status-report`) is read-only; everything else
  creates or mutates monday data — review what Claude proposes before approving.

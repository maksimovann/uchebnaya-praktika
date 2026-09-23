const partnerList = document.querySelector("#partner-list");
const partnerCount = document.querySelector("#partner-count");
const listStatus = document.querySelector("#list-status");
const emptyState = document.querySelector("#empty-state");
const searchInput = document.querySelector("#search-input");
const refreshButton = document.querySelector("#refresh-button");
const quantityFormatter = new Intl.NumberFormat("ru-RU");

let partners = [];

function addText(parent, tagName, className, value) {
  const element = document.createElement(tagName);
  element.className = className;
  element.textContent = value;
  parent.append(element);
  return element;
}

function addContactLink(parent, href, value) {
  const paragraph = document.createElement("p");
  const link = document.createElement("a");
  link.href = href;
  link.textContent = value;
  paragraph.append(link);
  parent.append(paragraph);
}

function createPartnerCard(partner) {
  const card = document.createElement("article");
  card.className = "partner-card";

  const top = document.createElement("div");
  top.className = "partner-card-top";
  addText(top, "h3", "partner-name", partner.company_name);
  addText(top, "span", "discount", `${partner.discount_percent}%`);
  card.append(top);

  const details = document.createElement("div");
  details.className = "partner-details";
  addText(details, "p", "", `ИНН: ${partner.inn}`);
  if (partner.phone) {
    addContactLink(details, `tel:${partner.phone.replace(/[^+\d]/g, "")}`, partner.phone);
  }
  if (partner.email) {
    addContactLink(details, `mailto:${partner.email}`, partner.email);
  }
  if (partner.rating !== null) {
    addText(details, "p", "", `Рейтинг: ${partner.rating}`);
  }
  addText(details, "p", "sales-total", `Объем продаж: ${quantityFormatter.format(partner.total_quantity)} ед.`);
  card.append(details);
  return card;
}

function renderPartners() {
  const query = searchInput.value.trim().toLocaleLowerCase("ru-RU");
  const visible = partners.filter((partner) => {
    const searchable = [partner.company_name, partner.inn, partner.phone, partner.email];
    return searchable.some((value) => String(value ?? "").toLocaleLowerCase("ru-RU").includes(query));
  });
  partnerList.replaceChildren(...visible.map(createPartnerCard));
  partnerCount.textContent = `(${partners.length})`;
  emptyState.hidden = visible.length > 0;
}

async function loadPartners() {
  refreshButton.disabled = true;
  listStatus.textContent = "Загрузка данных…";
  try {
    const response = await fetch("/api/partners", { cache: "no-store" });
    if (!response.ok) {
      throw new Error("Не удалось загрузить партнеров");
    }
    const data = await response.json();
    partners = data.partners;
    renderPartners();
    listStatus.textContent = `Всего партнеров: ${partners.length}`;
  } catch (error) {
    listStatus.textContent = error.message;
  } finally {
    refreshButton.disabled = false;
  }
}

refreshButton.addEventListener("click", loadPartners);
searchInput.addEventListener("input", renderPartners);

loadPartners();

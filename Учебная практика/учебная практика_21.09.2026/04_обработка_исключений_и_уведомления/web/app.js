const mainWindow = document.querySelector("#main-window");
const editWindow = document.querySelector("#partner-edit-window");
const pageTitle = document.querySelector("#page-title");
const formTitle = document.querySelector("#form-title");
const partnerList = document.querySelector("#partner-list");
const partnerCount = document.querySelector("#partner-count");
const listStatus = document.querySelector("#list-status");
const emptyState = document.querySelector("#empty-state");
const searchInput = document.querySelector("#search-input");
const refreshButton = document.querySelector("#refresh-button");
const addButton = document.querySelector("#add-button");
const backButton = document.querySelector("#back-button");
const cancelButton = document.querySelector("#cancel-button");
const partnerForm = document.querySelector("#partner-form");
const messageDialog = document.querySelector("#message-dialog");
const dialogIcon = document.querySelector("#dialog-icon");
const dialogTitle = document.querySelector("#dialog-title");
const dialogMessage = document.querySelector("#dialog-message");
const dialogActions = document.querySelector("#dialog-actions");
const quantityFormatter = new Intl.NumberFormat("ru-RU");

let partners = [];
let editingPartnerId = null;
let initialFormState = "";

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
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-label", `Редактировать ${partner.company_name}`);

  const top = document.createElement("div");
  top.className = "partner-card-top";
  addText(top, "h3", "partner-name", `${partner.partner_type || "ООО"} | ${partner.company_name}`);
  addText(top, "span", "discount", `${partner.discount_percent}%`);
  card.append(top);

  const details = document.createElement("div");
  details.className = "partner-details";
  addText(details, "p", "", `ИНН: ${partner.inn}`);
  if (partner.director_name) addText(details, "p", "", `Директор: ${partner.director_name}`);
  if (partner.phone) addContactLink(details, `tel:${partner.phone.replace(/[^+\d]/g, "")}`, partner.phone);
  if (partner.email) addContactLink(details, `mailto:${partner.email}`, partner.email);
  addText(details, "p", "", `Рейтинг: ${partner.rating ?? 0}`);
  addText(details, "p", "sales-total", `Объем продаж: ${quantityFormatter.format(partner.total_quantity)} ед.`);
  card.append(details);

  const openEditor = () => openEditWindow(partner.id);
  card.addEventListener("dblclick", openEditor);
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openEditor();
    }
  });
  card.addEventListener("click", openEditor);
  return card;
}

function renderPartners() {
  const query = searchInput.value.trim().toLocaleLowerCase("ru-RU");
  const visible = partners.filter((partner) => {
    const searchable = [partner.company_name, partner.partner_type, partner.inn, partner.phone, partner.email];
    return searchable.some((value) => String(value ?? "").toLocaleLowerCase("ru-RU").includes(query));
  });
  partnerList.replaceChildren(...visible.map(createPartnerCard));
  partnerCount.textContent = `(${partners.length})`;
  emptyState.hidden = visible.length > 0;
}

async function loadPartners() {
  refreshButton.disabled = true;
  listStatus.textContent = "Загрузка данных...";
  try {
    const response = await fetch("/api/partners", { cache: "no-store" });
    if (!response.ok) throw new Error("Не удалось загрузить партнеров. Проверьте подключение к базе и обновите страницу.");
    const data = await response.json();
    partners = data.partners;
    renderPartners();
    listStatus.textContent = `Всего партнеров: ${partners.length}`;
  } catch (error) {
    listStatus.textContent = error.message;
    showMessage("error", "Ошибка загрузки", error.message);
  } finally {
    refreshButton.disabled = false;
  }
}

function formData() {
  return Object.fromEntries(new FormData(partnerForm).entries());
}

function formSnapshot() {
  return JSON.stringify(formData());
}

function fillForm(partner = {}) {
  partnerForm.reset();
  for (const [name, value] of Object.entries(partner)) {
    const field = partnerForm.elements.namedItem(name);
    if (field) field.value = value ?? "";
  }
  partnerForm.elements.partner_type.value = partner.partner_type || "ООО";
  partnerForm.elements.rating.value = partner.rating ?? 0;
  initialFormState = formSnapshot();
}

// The view switch keeps the list and search state in memory while the editor is open.
async function openEditWindow(partnerId = null) {
  editingPartnerId = partnerId;
  if (partnerId === null) {
    fillForm();
    formTitle.textContent = "Добавление партнера";
    pageTitle.textContent = "Карточка партнера";
    document.title = "CRM: Карточка партнера [Добавление]";
  } else {
    try {
      const response = await fetch(`/api/partners/${partnerId}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Не удалось открыть карточку партнера.");
      fillForm(data.partner);
      formTitle.textContent = "Редактирование партнера";
      pageTitle.textContent = "Карточка партнера";
      document.title = "CRM: Карточка партнера [Редактирование]";
    } catch (error) {
      showMessage("error", "Ошибка базы данных", `${error.message} Проверьте подключение и повторите попытку.`);
      return;
    }
  }
  mainWindow.hidden = true;
  editWindow.hidden = false;
  partnerForm.elements.company_name.focus();
}

function closeEditWindow() {
  editWindow.hidden = true;
  mainWindow.hidden = false;
  pageTitle.textContent = "Реестр партнеров";
  document.title = "CRM: Реестр партнеров";
  editingPartnerId = null;
  addButton.focus();
}

function requestCloseEditor() {
  if (formSnapshot() === initialFormState) {
    closeEditWindow();
    return;
  }
  showMessage(
    "warning",
    "Несохраненные изменения",
    "Внесенные изменения будут безвозвратно потеряны. Вернуться в реестр без сохранения?",
    closeEditWindow,
  );
}

function showMessage(type, title, message, confirmAction = null) {
  const icons = { error: "×", warning: "!", information: "i" };
  dialogIcon.className = `dialog-icon dialog-icon-${type}`;
  dialogIcon.textContent = icons[type];
  dialogTitle.textContent = title;
  dialogMessage.textContent = message;
  dialogActions.replaceChildren();

  if (confirmAction) {
    const stayButton = document.createElement("button");
    stayButton.className = "button button-secondary";
    stayButton.textContent = "Остаться";
    stayButton.addEventListener("click", () => messageDialog.close());
    const confirmButton = document.createElement("button");
    confirmButton.className = "button button-danger";
    confirmButton.textContent = "Выйти без сохранения";
    confirmButton.addEventListener("click", () => {
      messageDialog.close();
      confirmAction();
    });
    dialogActions.append(stayButton, confirmButton);
  } else {
    const okButton = document.createElement("button");
    okButton.className = "button button-primary";
    okButton.textContent = "Понятно";
    okButton.addEventListener("click", () => messageDialog.close());
    dialogActions.append(okButton);
  }
  messageDialog.showModal();
}

async function savePartner(event) {
  event.preventDefault();
  const payload = formData();
  const url = editingPartnerId === null ? "/api/partners" : `/api/partners/${editingPartnerId}`;
  const method = editingPartnerId === null ? "POST" : "PUT";
  try {
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Не удалось сохранить данные.");
    const action = editingPartnerId === null ? "добавлен" : "обновлен";
    initialFormState = formSnapshot();
    await loadPartners();
    closeEditWindow();
    showMessage("information", "Сохранение выполнено", `Партнер успешно ${action}. Реестр обновлен.`);
  } catch (error) {
    showMessage("error", "Ошибка сохранения", error.message);
  }
}

refreshButton.addEventListener("click", loadPartners);
searchInput.addEventListener("input", renderPartners);
addButton.addEventListener("click", () => openEditWindow());
backButton.addEventListener("click", requestCloseEditor);
cancelButton.addEventListener("click", requestCloseEditor);
partnerForm.addEventListener("submit", savePartner);

loadPartners();

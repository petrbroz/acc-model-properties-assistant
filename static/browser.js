export async function initBrowser(credentials, onSelectionChanged) {
    const headers = { "Authorization": `Bearer ${credentials.access_token}` };
    const { data: hubs } = await fetch("/hubs", { headers }).then(resp => resp.json());
    const $tree = document.querySelector("#browser > sl-tree");
    for (const hub of hubs) {
        $tree.append(createTreeItem(`hub|${hub.id}`, hub.attributes.name, "cloud", true));
    }
    $tree.addEventListener("sl-selection-change", function ({ detail }) {
        if (detail.selection.length === 1 && detail.selection[0].id.startsWith("itm|")) {
            const [, hubId, projectId, itemId, urn] = detail.selection[0].id.split("|");
            const versionId = atob(urn.replace("_", "/"));
            onSelectionChanged({ hubId, projectId, itemId, versionId, urn });
        }
    });

    function createTreeItem(id, text, icon, children = false) {
        const item = document.createElement("sl-tree-item");
        item.id = id;
        item.innerHTML = `<sl-icon name="${icon}"></sl-icon><span style="white-space: nowrap">${text}</span>`;
        if (children) {
            item.lazy = true;
            item.addEventListener("sl-lazy-load", async function (ev) {
                ev.stopPropagation();
                item.lazy = false;
                const tokens = item.id.split("|");
                switch (tokens[0]) {
                    case "hub": {
                        const { data: projects } = await fetch(`/hubs/${tokens[1]}/projects`, { headers }).then(resp => resp.json());
                        item.append(...projects.map(project => createTreeItem(`prj|${tokens[1]}|${project.id}`, project.attributes.name, "building", true)));
                        break;
                    }
                    case "prj": {
                        const { data: folders } = await fetch(`/hubs/${tokens[1]}/projects/${tokens[2]}/contents`, { headers }).then(resp => resp.json());
                        item.append(...folders.map(folder => createTreeItem(`fld|${tokens[1]}|${tokens[2]}|${folder.id}`, folder.attributes.displayName, "folder", true)));
                        break;
                    }
                    case "fld": {
                        const { data: contents, included } = await fetch(`/hubs/${tokens[1]}/projects/${tokens[2]}/contents?folder_id=${tokens[3]}`, { headers }).then(resp => resp.json());
                        const folders = contents.filter(entry => entry.type === "folders");
                        item.append(...folders.map(folder => createTreeItem(`fld|${tokens[1]}|${tokens[2]}|${folder.id}`, folder.attributes.displayName, "folder", true)));
                        const designs = contents.filter(entry => entry.type === "items");
                        for (const [i, design] of designs.entries()) {
                            const urn = included[i].relationships.derivatives.data.id;
                            item.append(createTreeItem(`itm|${tokens[1]}|${tokens[2]}|${design.id}|${urn}`, design.attributes.displayName, "file-earmark-richtext", false));
                        }
                        break;
                    }
                }
            });
        }
        return item;
    }
}
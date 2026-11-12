// Adapter dữ liệu HTTP duy nhất được sử dụng bởi các component và context của React.
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function requestJson(path, { method = "GET", body, signal } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      body,
      signal,
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError("Không kết nối được máy chủ. Kiểm tra kết nối và thử lại.", 0);
  }
  let data;
  try {
    data = await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError("Dữ liệu trả về không hợp lệ. Vui lòng thử lại.", response.status);
  }
  if (!response.ok) {
    throw new ApiError(data?.error?.message || "Không thể tải dữ liệu. Vui lòng thử lại.", response.status);
  }
  return data;
}

function getJson(path, options = {}) {
  return requestJson(path, options);
}

function itemsOf(data) {
  if (!Array.isArray(data?.items) || data.total !== data.items.length) {
    throw new ApiError("Danh sách trả về không hợp lệ. Vui lòng thử lại.", 502);
  }
  return data.items;
}

function imageFromApi(image, name) {
  if (!image) return null;
  if (typeof image.url !== "string" || !image.url.startsWith("/api/images/")) {
    throw new ApiError("Địa chỉ ảnh không hợp lệ.", 502);
  }
  return {
    id: image.id, src: image.url, alt: image.caption || name,
    caption: image.caption || name, order: image.order
  };
}

function matchedEvidenceFromApi(evidence, name) {
  if (!evidence) return null;
  return {
    type: evidence.type,
    descId: evidence.desc_id ?? null,
    snippet: evidence.snippet ?? null,
    image: evidence.image ? imageFromApi(evidence.image, evidence.snippet || name) : null,
  };
}

// Giữ nguyên cấu trúc dữ liệu cho giao diện component; các giá trị hiển thị được lấy từ API.
function placeFromApi(item, boundaryMode = "after") {
  const before = boundaryMode === "before";
  const coverImage = imageFromApi(item.cover_image, item.name);
  const images = item.images?.map((image) => imageFromApi(image, item.name)) ?? (coverImage ? [coverImage] : []);
  const matchedEvidence = matchedEvidenceFromApi(item.matched_evidence, item.name);
  return {
    place_id: item.id,
    rank: typeof item.rank === "number" ? item.rank : null,
    score: typeof item.score === "number" ? item.score : null,
    matchedEvidence,
    name: item.name,
    provinceBefore: item.province_former.name,
    provinceAfter: item.province_current.name,
    province: before ? item.province_former.name : item.province_current.name,
    address: item.address,
    type: item.tourism_types.map((type) => type.name).join(" · "),
    tourismTypes: item.tourism_types,
    coordinates: [item.location.lat, item.location.lng],
    coverImage,
    images,
    other_names: item.other_names ?? [],
    descriptionParts: item.description_parts ?? [],
  };
}

export async function listPlaces(filters = {}, options = {}) {
  const params = new URLSearchParams();
  if (filters.province) params.set("province_id", filters.province);
  if (filters.type) params.set("tourism_type_id", filters.type);
  const suffix = params.size ? `?${params}` : "";
  const data = await getJson(`/api/places${suffix}`, options);
  return itemsOf(data).map((item) => placeFromApi(item, filters.boundaryMode));
}

export async function searchPlaces({ text = "", image = null, filters = {} } = {}, options = {}) {
  const formData = new FormData();
  const trimmed = text.trim();
  if (trimmed) formData.append("query_text", trimmed);
  const imageFile = image?.file ?? image;
  if (imageFile) formData.append("query_image", imageFile);
  if (filters.province) formData.append("province_id", filters.province);
  if (filters.type) formData.append("tourism_type_id", filters.type);
  const data = await requestJson("/api/search", {
    method: "POST",
    body: formData,
    signal: options.signal,
  });
  return itemsOf(data).map((item) => placeFromApi(item, filters.boundaryMode));
}

export async function getPlaceDetail(placeId, options = {}) {
  try {
    return placeFromApi(await getJson(`/api/places/${encodeURIComponent(placeId)}`, options));
  } catch (error) {
    if (error.status === 404) return null;
    throw error;
  }
}

export async function getFilters({ boundaryMode = "after", signal } = {}) {
  const scheme = boundaryMode === "before" ? "former" : "current";
  const [provinces, types] = await Promise.all([
    getJson(`/api/provinces?scheme=${scheme}`, { signal }),
    getJson("/api/tourism-types", { signal }),
  ]);
  return { provinces: itemsOf(provinces), types: itemsOf(types) };
}

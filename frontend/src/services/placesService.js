// Adapter dữ liệu HTTP duy nhất được sử dụng bởi các component và context của React.
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function getJson(path, { signal } = {}) {
  let response;
  try {
    response = await fetch(path, { signal, headers: { Accept: "application/json" } });
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

// Giữ nguyên cấu trúc dữ liệu cho giao diện component; các giá trị hiển thị được lấy từ API.
function placeFromApi(item, boundaryMode = "after") {
  const before = boundaryMode === "before";
  const coverImage = imageFromApi(item.cover_image, item.name);
  const images = item.images?.map((image) => imageFromApi(image, item.name)) ?? (coverImage ? [coverImage] : []);
  return {
    place_id: item.id,
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

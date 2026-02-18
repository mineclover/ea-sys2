import { useState } from 'react';
import {
  useBusinessModels,
  useBusinessModel,
  useBusinessTags,
  useCreateBusiness,
  useDeleteBusiness,
  useCreateTag,
  useDeleteTag
} from '@/api/hooks';
import { Card, Badge, ErrorBanner, EmptyState, LoadingSpinner } from '@/components/ui';
import { PageHeader } from '@/components/layout';

export default function BusinessModelEditor() {
  const [selectedBusinessId, setSelectedBusinessId] = useState<string | null>(null);
  const [newBusinessName, setNewBusinessName] = useState('');
  const [showCreateBusiness, setShowCreateBusiness] = useState(false);
  const [newTagName, setNewTagName] = useState('');
  const [showCreateTag, setShowCreateTag] = useState(false);

  const { data: businesses, isLoading: isLoadingBusinesses, error: businessesError } = useBusinessModels();
  const { data: selectedBusiness, isLoading: isLoadingBusiness, error: businessError } = useBusinessModel(selectedBusinessId || '');
  const { data: tags, isLoading: isLoadingTags, error: tagsError } = useBusinessTags(selectedBusinessId || '');

  const createBusiness = useCreateBusiness();
  const deleteBusiness = useDeleteBusiness();
  const createTag = useCreateTag();
  const deleteTag = useDeleteTag();

  const handleCreateBusiness = async () => {
    if (!newBusinessName.trim()) return;

    try {
      await createBusiness.mutateAsync({ name: newBusinessName.trim() });
      setNewBusinessName('');
      setShowCreateBusiness(false);
    } catch (error) {
      console.error('Failed to create business:', error);
    }
  };

  const handleDeleteBusiness = async (businessId: string) => {
    if (!confirm('Are you sure you want to delete this business model? This will also delete all associated tags.')) {
      return;
    }

    try {
      await deleteBusiness.mutateAsync(businessId);
      if (selectedBusinessId === businessId) {
        setSelectedBusinessId(null);
      }
    } catch (error) {
      console.error('Failed to delete business:', error);
    }
  };

  const handleCreateTag = async () => {
    if (!selectedBusinessId || !newTagName.trim()) return;

    try {
      await createTag.mutateAsync({
        bid: selectedBusinessId,
        data: { tag: newTagName.trim() }
      });
      setNewTagName('');
      setShowCreateTag(false);
    } catch (error) {
      console.error('Failed to create tag:', error);
    }
  };

  const handleDeleteTag = async (tagName: string) => {
    if (!selectedBusinessId || !confirm('Are you sure you want to delete this tag schema?')) {
      return;
    }

    try {
      await deleteTag.mutateAsync({ bid: selectedBusinessId, tag: tagName });
    } catch (error) {
      console.error('Failed to delete tag:', error);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader metaKey="admin.business" compact />
      <div style={{ display: 'flex', gap: '24px', flex: 1, overflow: 'auto', padding: '16px' }}>
      {/* Left Panel - Business Model List */}
      <div style={{ width: '320px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <Card>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '16px'
          }}>
            <h2 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--foreground)' }}>
              Business Models
            </h2>
            <button
              onClick={() => setShowCreateBusiness(true)}
              style={{
                padding: '6px 12px',
                backgroundColor: 'var(--primary)',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                fontSize: '14px',
                fontWeight: '500',
                cursor: 'pointer'
              }}
            >
              + New
            </button>
          </div>

          {businessesError && (
            <ErrorBanner message={businessesError instanceof Error ? businessesError.message : 'Failed to load businesses'} />
          )}

          {isLoadingBusinesses ? (
            <LoadingSpinner />
          ) : businesses && businesses.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {businesses.map((business) => (
                <div
                  key={business.bid}
                  onClick={() => setSelectedBusinessId(business.bid)}
                  style={{
                    padding: '12px',
                    backgroundColor: selectedBusinessId === business.bid ? 'var(--muted)' : 'var(--secondary)',
                    border: `1px solid ${selectedBusinessId === business.bid ? 'var(--primary)' : 'var(--border)'}`,
                    borderRadius: '6px',
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    transition: 'all 0.2s'
                  }}
                >
                  <div>
                    <div style={{ fontWeight: '500', color: 'var(--foreground)', fontSize: '14px' }}>
                      {business.name}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginTop: '4px' }}>
                      {business.tag_count || 0} tags
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteBusiness(business.bid);
                    }}
                    style={{
                      padding: '4px 8px',
                      backgroundColor: 'transparent',
                      color: 'var(--destructive)',
                      border: '1px solid var(--destructive)',
                      borderRadius: '4px',
                      fontSize: '12px',
                      cursor: 'pointer'
                    }}
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState message="No business models found" />
          )}

          {showCreateBusiness && (
            <div style={{
              marginTop: '16px',
              padding: '12px',
              backgroundColor: 'var(--secondary)',
              borderRadius: '6px',
              border: '1px solid var(--border)'
            }}>
              <input
                type="text"
                value={newBusinessName}
                onChange={(e) => setNewBusinessName(e.target.value)}
                placeholder="Business model name"
                style={{
                  width: '100%',
                  padding: '8px',
                  border: '1px solid var(--input)',
                  borderRadius: '4px',
                  fontSize: '14px',
                  marginBottom: '8px'
                }}
              />
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={handleCreateBusiness}
                  disabled={!newBusinessName.trim() || createBusiness.isPending}
                  style={{
                    flex: 1,
                    padding: '6px',
                    backgroundColor: 'var(--status-success-text)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    fontSize: '14px',
                    cursor: 'pointer',
                    opacity: !newBusinessName.trim() || createBusiness.isPending ? 0.5 : 1
                  }}
                >
                  Create
                </button>
                <button
                  onClick={() => {
                    setShowCreateBusiness(false);
                    setNewBusinessName('');
                  }}
                  style={{
                    flex: 1,
                    padding: '6px',
                    backgroundColor: 'var(--border)',
                    color: 'var(--foreground)',
                    border: 'none',
                    borderRadius: '4px',
                    fontSize: '14px',
                    cursor: 'pointer'
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </Card>
      </div>

      {/* Right Panel - Business Detail and Tags */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '16px', overflow: 'auto' }}>
        {!selectedBusinessId ? (
          <Card>
            <EmptyState message="Select a business model to view details" />
          </Card>
        ) : (
          <>
            {/* Business Detail */}
            <Card>
              <h2 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--foreground)', marginBottom: '16px' }}>
                Business Model Details
              </h2>

              {businessError && (
                <ErrorBanner message={businessError instanceof Error ? businessError.message : 'Failed to load business'} />
              )}

              {isLoadingBusiness ? (
                <LoadingSpinner />
              ) : selectedBusiness ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div>
                    <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginBottom: '4px' }}>Name</div>
                    <div style={{ fontSize: '14px', color: 'var(--foreground)', fontWeight: '500' }}>
                      {selectedBusiness.name}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginBottom: '4px' }}>ID</div>
                    <div style={{ fontSize: '13px', color: 'var(--muted-foreground)', fontFamily: 'monospace' }}>
                      {selectedBusiness.bid}
                    </div>
                  </div>
                  {selectedBusiness.description && (
                    <div>
                      <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginBottom: '4px' }}>Description</div>
                      <div style={{ fontSize: '14px', color: 'var(--foreground)' }}>
                        {selectedBusiness.description}
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
            </Card>

            {/* Tag Schemas */}
            <Card>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '16px'
              }}>
                <h2 style={{ fontSize: '16px', fontWeight: '600', color: 'var(--foreground)' }}>
                  Tag Schemas
                </h2>
                <button
                  onClick={() => setShowCreateTag(true)}
                  style={{
                    padding: '6px 12px',
                    backgroundColor: 'var(--primary)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '6px',
                    fontSize: '14px',
                    fontWeight: '500',
                    cursor: 'pointer'
                  }}
                >
                  + New Tag
                </button>
              </div>

              {tagsError && (
                <ErrorBanner message={tagsError instanceof Error ? tagsError.message : 'Failed to load tags'} />
              )}

              {isLoadingTags ? (
                <LoadingSpinner />
              ) : tags && tags.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {tags.map((tag) => (
                    <div
                      key={tag.tag}
                      style={{
                        padding: '16px',
                        backgroundColor: 'var(--secondary)',
                        border: '1px solid var(--border)',
                        borderRadius: '6px'
                      }}
                    >
                      <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'start',
                        marginBottom: '12px'
                      }}>
                        <div>
                          <div style={{ fontSize: '14px', fontWeight: '600', color: 'var(--foreground)' }}>
                            {tag.tag}
                          </div>
                          {tag.kernel_ref && (
                            <div style={{ marginTop: '6px' }}>
                              <Badge label={tag.kernel_ref} bg="var(--status-info-bg)" color="var(--primary)" />
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => handleDeleteTag(tag.tag)}
                          style={{
                            padding: '4px 8px',
                            backgroundColor: 'transparent',
                            color: 'var(--destructive)',
                            border: '1px solid var(--destructive)',
                            borderRadius: '4px',
                            fontSize: '12px',
                            cursor: 'pointer'
                          }}
                        >
                          Delete
                        </button>
                      </div>

                      {tag.fields && tag.fields.length > 0 && (
                        <div style={{ marginBottom: '12px' }}>
                          <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginBottom: '6px' }}>
                            Fields
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                            {tag.fields.map((field, idx) => (
                              <Badge key={idx} label={`${field.name}: ${field.type}`} bg="var(--accent)" color="var(--muted-foreground)" />
                            ))}
                          </div>
                        </div>
                      )}

                      {tag.indexes && tag.indexes.length > 0 && (
                        <div style={{ marginBottom: '12px' }}>
                          <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginBottom: '6px' }}>
                            Indexes
                          </div>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                            {tag.indexes.map((index, idx) => (
                              <Badge key={idx} label={`${index.name}: ${index.keyPath}`} bg="var(--status-success-bg)" color="var(--status-success-text)" />
                            ))}
                          </div>
                        </div>
                      )}

                      {tag.keyPath && (
                        <div>
                          <div style={{ fontSize: '12px', color: 'var(--muted-foreground)', marginBottom: '4px' }}>
                            Key Path
                          </div>
                          <div style={{
                            fontSize: '13px',
                            color: 'var(--foreground)',
                            fontFamily: 'monospace',
                            backgroundColor: 'var(--card)',
                            padding: '8px',
                            borderRadius: '4px',
                            border: '1px solid var(--border)'
                          }}>
                            {tag.keyPath}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState message="No tag schemas found" />
              )}

              {showCreateTag && (
                <div style={{
                  marginTop: '16px',
                  padding: '12px',
                  backgroundColor: 'var(--secondary)',
                  borderRadius: '6px',
                  border: '1px solid var(--border)'
                }}>
                  <input
                    type="text"
                    value={newTagName}
                    onChange={(e) => setNewTagName(e.target.value)}
                    placeholder="Tag schema name"
                    style={{
                      width: '100%',
                      padding: '8px',
                      border: '1px solid var(--input)',
                      borderRadius: '4px',
                      fontSize: '14px',
                      marginBottom: '8px'
                    }}
                  />
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={handleCreateTag}
                      disabled={!newTagName.trim() || createTag.isPending}
                      style={{
                        flex: 1,
                        padding: '6px',
                        backgroundColor: 'var(--status-success-text)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        fontSize: '14px',
                        cursor: 'pointer',
                        opacity: !newTagName.trim() || createTag.isPending ? 0.5 : 1
                      }}
                    >
                      Create
                    </button>
                    <button
                      onClick={() => {
                        setShowCreateTag(false);
                        setNewTagName('');
                      }}
                      style={{
                        flex: 1,
                        padding: '6px',
                        backgroundColor: 'var(--border)',
                        color: 'var(--foreground)',
                        border: 'none',
                        borderRadius: '4px',
                        fontSize: '14px',
                        cursor: 'pointer'
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </Card>
          </>
        )}
      </div>
      </div>
    </div>
  );
}
